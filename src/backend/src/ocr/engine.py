"""
Core OCR engine module orchestrating document processing and extraction.

This module provides enterprise-grade OCR processing capabilities with comprehensive
error handling, performance monitoring, and quality validation. Supports multiple
extraction strategies and document types.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import logging  # version: 3.11+
from typing import Dict, Any, Optional, List, Type  # version: 3.11+
import time  # version: 3.11+
import psutil  # version: 5.9.0
from PIL import Image  # version: 10.0.0

from ocr.processors import OCRProcessor
from ocr.validators import OCRTaskConfigSchema
from ocr.extractors import (
    BaseExtractor,
    TextExtractor,
    TableExtractor,
    EXTRACTION_TYPES
)
from core.exceptions import ValidationException

# Registry mapping extraction types to their implementations
EXTRACTOR_REGISTRY: Dict[str, str] = {
    'text': 'TextExtractor',
    'table': 'TableExtractor',
    'mixed': 'MixedContentExtractor',
    'form': 'FormExtractor',
    'receipt': 'ReceiptExtractor'
}

# Default engine configuration
DEFAULT_ENGINE_CONFIG = {
    'max_workers': 4,
    'timeout_seconds': 300,
    'retry_attempts': 3,
    'backoff_factor': 2,
    'confidence_threshold': 0.98,
    'max_memory_mb': 2048,
    'monitoring_interval_seconds': 60
}

class OCREngine:
    """
    Enhanced OCR engine orchestrating document processing with advanced features.
    
    Provides thread-safe document processing with performance monitoring,
    resource management, and comprehensive error handling.
    """
    
    def __init__(self, config: OCRTaskConfigSchema) -> None:
        """
        Initialize OCR engine with configuration and monitoring.
        
        Args:
            config: Validated configuration schema
            
        Raises:
            ValidationException: If configuration is invalid
        """
        self._config = config
        self._logger = logging.getLogger(__name__)
        
        # Initialize processing lock for thread safety
        self._engine_lock = asyncio.Lock()
        
        # Initialize extractors registry
        self._extractors: Dict[str, Type[BaseExtractor]] = {
            'text': TextExtractor(config),
            'table': TableExtractor(config)
        }
        
        # Initialize performance metrics
        self._performance_metrics = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'avg_processing_time': 0.0,
            'peak_memory_usage': 0.0
        }
        
        # Initialize error tracking
        self._error_counts: Dict[str, int] = {
            'validation_errors': 0,
            'processing_errors': 0,
            'timeout_errors': 0,
            'memory_errors': 0
        }
        
        self._logger.info("OCR Engine initialized with configuration: %s", 
                         config.dict(exclude_none=True))

    async def async_process_document(self, task_id: str, extraction_type: str) -> Dict[str, Any]:
        """
        Process document asynchronously with enhanced safety and monitoring.
        
        Args:
            task_id: Unique identifier for the processing task
            extraction_type: Type of extraction to perform
            
        Returns:
            Dict[str, Any]: Processing results and metadata
            
        Raises:
            ValidationException: If processing fails
        """
        start_time = time.time()
        
        try:
            # Acquire processing lock with timeout
            async with self._engine_lock:
                self._logger.info("Starting async processing for task %s", task_id)
                
                # Monitor memory usage
                if not self._check_memory_usage():
                    raise ValidationException(
                        "Insufficient memory available",
                        {"current_usage": self._get_memory_usage()}
                    )
                
                # Process document
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.process_document,
                    task_id,
                    extraction_type
                )
                
                # Update performance metrics
                processing_time = time.time() - start_time
                self._update_performance_metrics(processing_time, success=True)
                
                self._logger.info("Async processing completed for task %s in %.2fs",
                                task_id, processing_time)
                
                return result
                
        except Exception as e:
            processing_time = time.time() - start_time
            self._update_performance_metrics(processing_time, success=False)
            self._error_counts['processing_errors'] += 1
            
            self._logger.error("Async processing failed for task %s: %s",
                             task_id, str(e))
            raise ValidationException(
                "Async document processing failed",
                {
                    "task_id": task_id,
                    "error": str(e),
                    "processing_time": processing_time
                }
            )

    def process_document(self, task_id: str, extraction_type: str) -> Dict[str, Any]:
        """
        Process document with comprehensive error handling and validation.
        
        Args:
            task_id: Unique identifier for the processing task
            extraction_type: Type of extraction to perform
            
        Returns:
            Dict[str, Any]: Processing results with quality metrics
            
        Raises:
            ValidationException: If processing fails
        """
        start_time = time.time()
        
        try:
            # Validate extraction type
            if extraction_type not in EXTRACTOR_REGISTRY:
                raise ValidationException(
                    "Unsupported extraction type",
                    {
                        "type": extraction_type,
                        "supported_types": list(EXTRACTOR_REGISTRY.keys())
                    }
                )
            
            # Get appropriate extractor
            extractor = self._extractors.get(extraction_type)
            if not extractor:
                raise ValidationException(
                    "Extractor not initialized",
                    {"extraction_type": extraction_type}
                )
            
            # Load and validate input image
            image = self._load_image(self._config.source_path)
            
            # Process with retry logic
            result = self._process_with_retry(
                extractor.extract,
                image,
                max_attempts=DEFAULT_ENGINE_CONFIG['retry_attempts']
            )
            
            # Validate results
            if not self._validate_results(result):
                raise ValidationException(
                    "Processing results failed validation",
                    {"confidence": result.get('confidence')}
                )
            
            # Add processing metadata
            processing_time = time.time() - start_time
            result.update({
                'task_id': task_id,
                'processing_time': processing_time,
                'memory_usage': self._get_memory_usage(),
                'extraction_type': extraction_type
            })
            
            self._logger.info("Document processing completed for task %s in %.2fs",
                            task_id, processing_time)
            
            return result
            
        except Exception as e:
            self._error_counts['processing_errors'] += 1
            self._logger.error("Document processing failed for task %s: %s",
                             task_id, str(e))
            raise ValidationException(
                "Document processing failed",
                {
                    "task_id": task_id,
                    "error": str(e),
                    "processing_time": time.time() - start_time
                }
            )

    def _load_image(self, image_path: str) -> Image.Image:
        """Helper method to load and validate input image."""
        try:
            image = Image.open(image_path)
            return image
        except Exception as e:
            self._error_counts['validation_errors'] += 1
            raise ValidationException(
                "Failed to load input image",
                {"path": image_path, "error": str(e)}
            )

    def _process_with_retry(self, process_func: callable, image: Image.Image,
                          max_attempts: int) -> Dict[str, Any]:
        """Helper method implementing retry logic with exponential backoff."""
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                return process_func(image)
            except Exception as e:
                last_error = e
                wait_time = DEFAULT_ENGINE_CONFIG['backoff_factor'] ** attempt
                time.sleep(wait_time)
                
        raise ValidationException(
            "Processing failed after retries",
            {"max_attempts": max_attempts, "last_error": str(last_error)}
        )

    def _validate_results(self, results: Dict[str, Any]) -> bool:
        """Helper method to validate processing results."""
        if not results:
            return False
            
        confidence = results.get('confidence', 0)
        return confidence >= DEFAULT_ENGINE_CONFIG['confidence_threshold']

    def _check_memory_usage(self) -> bool:
        """Helper method to check available memory."""
        current_usage = self._get_memory_usage()
        return current_usage < DEFAULT_ENGINE_CONFIG['max_memory_mb']

    def _get_memory_usage(self) -> float:
        """Helper method to get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)

    def _update_performance_metrics(self, processing_time: float, success: bool) -> None:
        """Helper method to update performance tracking metrics."""
        self._performance_metrics['total_tasks'] += 1
        if success:
            self._performance_metrics['successful_tasks'] += 1
        else:
            self._performance_metrics['failed_tasks'] += 1
            
        # Update average processing time
        current_avg = self._performance_metrics['avg_processing_time']
        total_tasks = self._performance_metrics['total_tasks']
        new_avg = ((current_avg * (total_tasks - 1)) + processing_time) / total_tasks
        self._performance_metrics['avg_processing_time'] = new_avg
        
        # Update peak memory usage
        current_memory = self._get_memory_usage()
        self._performance_metrics['peak_memory_usage'] = max(
            self._performance_metrics['peak_memory_usage'],
            current_memory
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics and statistics.
        
        Returns:
            Dict[str, Any]: Current performance metrics
        """
        return {
            'metrics': self._performance_metrics.copy(),
            'errors': self._error_counts.copy(),
            'current_memory_usage': self._get_memory_usage()
        }

__all__ = ['OCREngine', 'EXTRACTOR_REGISTRY', 'DEFAULT_ENGINE_CONFIG']