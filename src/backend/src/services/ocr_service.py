"""
OCR service implementation orchestrating OCR processing tasks.

This service implements the TaskProcessor interface to provide enterprise-grade OCR
processing capabilities with comprehensive error handling, performance monitoring,
and quality validation.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import logging  # version: 3.11+
from typing import Dict, Any, Optional  # version: 3.11+

from core.interfaces import TaskProcessor
from core.types import TaskType, TaskConfig, TaskResult
from core.exceptions import ValidationException, StorageException
from ocr.engine import OCREngine
from ocr.validators import validate_ocr_task, OCRTaskConfigSchema
from storage.cloud_storage import CloudStorageBackend

# Default OCR service configuration
DEFAULT_OCR_CONFIG = {
    'timeout_seconds': 300,  # 5 minutes max processing time
    'max_retries': 3,
    'quality_threshold': 0.98,  # 98% minimum quality requirement
    'memory_limit_mb': 2048,  # 2GB memory limit
    'processing_batch_size': 10,
    'error_retry_delay_ms': 1000
}

class OCRService(TaskProcessor):
    """
    Enterprise-grade OCR service implementing TaskProcessor interface.
    
    Provides robust OCR processing capabilities with enhanced error handling,
    performance monitoring, and quality validation.
    """
    
    def __init__(self, storage_backend: CloudStorageBackend, config: Dict[str, Any]) -> None:
        """
        Initialize OCR service with storage and configuration.
        
        Args:
            storage_backend: Cloud storage backend for data persistence
            config: Service configuration parameters
            
        Raises:
            ValidationException: If configuration is invalid
        """
        self._storage = storage_backend
        self._config = {**DEFAULT_OCR_CONFIG, **config}
        self._logger = logging.getLogger(__name__)
        
        # Initialize performance metrics
        self._metrics = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'avg_processing_time': 0.0,
            'peak_memory_usage': 0.0,
            'quality_scores': []
        }
        
        self._logger.info("Initialized OCR service with configuration: %s", 
                         self._config)

    @property
    def processor_type(self) -> TaskType:
        """Get the processor type."""
        return "ocr"

    async def process(self, task_config: TaskConfig) -> TaskResult:
        """
        Process OCR task with comprehensive error handling and monitoring.
        
        Args:
            task_config: Configuration for the OCR task
            
        Returns:
            TaskResult: Processing results with quality metrics
            
        Raises:
            ValidationException: If task validation fails
            StorageException: If storage operations fail
        """
        start_time = asyncio.get_event_loop().time()
        task_id = str(task_config.get('id', 'unknown'))
        
        try:
            self._logger.info("Starting OCR processing for task %s", task_id)
            
            # Validate task configuration
            validated_config = validate_ocr_task(task_config)
            config_schema = OCRTaskConfigSchema(**validated_config)
            
            # Initialize OCR engine with validated configuration
            engine = OCREngine(config_schema)
            
            # Process document with timeout
            async with asyncio.timeout(self._config['timeout_seconds']):
                # Retrieve document from storage
                async with self._storage.retrieve_object(config_schema.source_path) as doc_data:
                    # Process with retry logic
                    for attempt in range(self._config['max_retries']):
                        try:
                            ocr_result = await engine.async_process_document(
                                task_id=task_id,
                                extraction_type=config_schema.processing_options.get('extraction_type', 'text')
                            )
                            
                            # Validate quality meets threshold
                            if ocr_result['confidence'] < self._config['quality_threshold'] * 100:
                                raise ValidationException(
                                    "OCR quality below threshold",
                                    {
                                        "confidence": ocr_result['confidence'],
                                        "threshold": self._config['quality_threshold'] * 100
                                    }
                                )
                            
                            break
                        except Exception as e:
                            if attempt == self._config['max_retries'] - 1:
                                raise
                            await asyncio.sleep(self._config['error_retry_delay_ms'] / 1000)
                            
                    # Store results in cloud storage
                    result_object = await self._storage.store_object(
                        data=ocr_result['text'].encode('utf-8'),
                        metadata={
                            'task_id': task_id,
                            'content_type': 'text/plain',
                            'confidence': ocr_result['confidence'],
                            'word_count': len(ocr_result['text'].split()),
                            'processing_options': config_schema.processing_options
                        }
                    )
                    
                    # Update performance metrics
                    processing_time = asyncio.get_event_loop().time() - start_time
                    self._update_metrics(processing_time, ocr_result['confidence'])
                    
                    self._logger.info(
                        "OCR processing completed for task %s in %.2fs with confidence %.2f%%",
                        task_id, processing_time, ocr_result['confidence']
                    )
                    
                    # Return processing results
                    return {
                        'status': 'completed',
                        'result': {
                            'storage_path': result_object.storage_path,
                            'content_type': result_object.content_type,
                            'confidence': ocr_result['confidence'],
                            'word_count': len(ocr_result['text'].split()),
                            'processing_time': processing_time
                        },
                        'metadata': {
                            'quality_score': ocr_result['confidence'] / 100,
                            'performance_metrics': self.get_performance_metrics()
                        }
                    }
                    
        except asyncio.TimeoutError:
            self._logger.error("OCR processing timeout for task %s", task_id)
            raise ValidationException(
                "OCR processing timeout",
                {
                    "task_id": task_id,
                    "timeout": self._config['timeout_seconds']
                }
            )
            
        except Exception as e:
            self._logger.error("OCR processing failed for task %s: %s", task_id, str(e))
            self._metrics['failed_tasks'] += 1
            raise ValidationException(
                "OCR processing failed",
                {
                    "task_id": task_id,
                    "error": str(e),
                    "processing_time": asyncio.get_event_loop().time() - start_time
                }
            )

    def _update_metrics(self, processing_time: float, quality_score: float) -> None:
        """Update service performance metrics."""
        self._metrics['total_tasks'] += 1
        self._metrics['successful_tasks'] += 1
        
        # Update average processing time
        total_tasks = self._metrics['total_tasks']
        current_avg = self._metrics['avg_processing_time']
        self._metrics['avg_processing_time'] = (
            (current_avg * (total_tasks - 1) + processing_time) / total_tasks
        )
        
        # Track quality scores
        self._metrics['quality_scores'].append(quality_score)
        
        # Update peak memory usage
        import psutil
        current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        self._metrics['peak_memory_usage'] = max(
            self._metrics['peak_memory_usage'],
            current_memory
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return {
            'task_counts': {
                'total': self._metrics['total_tasks'],
                'successful': self._metrics['successful_tasks'],
                'failed': self._metrics['failed_tasks']
            },
            'processing_time': {
                'average_seconds': self._metrics['avg_processing_time']
            },
            'quality': {
                'average_score': sum(self._metrics['quality_scores']) / len(self._metrics['quality_scores'])
                if self._metrics['quality_scores'] else 0
            },
            'resource_usage': {
                'peak_memory_mb': self._metrics['peak_memory_usage']
            }
        }