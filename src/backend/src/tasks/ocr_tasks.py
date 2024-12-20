"""
OCR task implementation with enhanced quality validation and monitoring.

This module implements OCR-specific task processing with comprehensive error handling,
performance monitoring, and quality validation capabilities.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import logging  # version: 3.11+
from typing import Dict, Optional, Any  # version: 3.11+

from tasks.base import BaseTask, BaseTaskExecutor
from ocr.engine import OCREngine
from services.ocr_service import OCRService
from core.exceptions import ValidationException, TaskException

# Configure logging
LOGGER = logging.getLogger(__name__)

# Default OCR task configuration
DEFAULT_TASK_CONFIG = {
    'extraction_type': 'text',  # Default to text extraction
    'timeout_seconds': 300,     # 5 minutes timeout
    'retry_attempts': 3,        # Maximum retry attempts
    'quality_threshold': 0.98,  # 98% quality requirement
    'max_memory_mb': 2048,     # 2GB memory limit
    'batch_size': 10           # Processing batch size
}

class OCRTask(BaseTask):
    """
    Enhanced OCR task implementation with quality validation and monitoring.
    
    Extends BaseTask with OCR-specific processing capabilities including
    quality validation, performance monitoring, and resource tracking.
    """
    
    def __init__(self, ocr_service: OCRService) -> None:
        """
        Initialize OCR task with service instance and monitoring.
        
        Args:
            ocr_service: OCR service instance for processing
            
        Raises:
            ValidationException: If service initialization fails
        """
        super().__init__()
        self._ocr_service = ocr_service
        self._logger = logging.getLogger(__name__)
        
        # Initialize performance metrics
        self._metrics = {
            'processed_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'avg_processing_time': 0.0,
            'quality_scores': [],
            'resource_usage': {
                'peak_memory_mb': 0,
                'avg_memory_mb': 0
            }
        }
        
        # Register task processors
        self.register_processor(ocr_service)
        
        self._logger.info("Initialized OCR task handler with quality threshold: %.2f",
                         DEFAULT_TASK_CONFIG['quality_threshold'])

    @property
    def task_type(self) -> str:
        """Get the task type."""
        return "ocr"

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Enhanced configuration validation with quality checks.
        
        Args:
            config: Task configuration to validate
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValidationException: If configuration is invalid
        """
        try:
            # Validate required fields
            required_fields = ['source_path', 'output_format']
            for field in required_fields:
                if field not in config:
                    raise ValidationException(
                        f"Missing required configuration field: {field}",
                        {"field": field}
                    )
            
            # Validate file path exists
            source_path = config['source_path']
            if not await self._validate_file_exists(source_path):
                raise ValidationException(
                    "Source file not found",
                    {"path": source_path}
                )
            
            # Validate extraction type
            extraction_type = config.get('extraction_type', DEFAULT_TASK_CONFIG['extraction_type'])
            if extraction_type not in ['text', 'table', 'mixed']:
                raise ValidationException(
                    "Invalid extraction type",
                    {
                        "type": extraction_type,
                        "supported_types": ['text', 'table', 'mixed']
                    }
                )
            
            # Validate quality threshold
            quality_threshold = config.get('quality_threshold', 
                                        DEFAULT_TASK_CONFIG['quality_threshold'])
            if not (0 < quality_threshold <= 1):
                raise ValidationException(
                    "Invalid quality threshold",
                    {
                        "threshold": quality_threshold,
                        "valid_range": "(0, 1]"
                    }
                )
            
            # Validate resource limits
            memory_limit = config.get('max_memory_mb', 
                                    DEFAULT_TASK_CONFIG['max_memory_mb'])
            if memory_limit <= 0:
                raise ValidationException(
                    "Invalid memory limit",
                    {"limit_mb": memory_limit}
                )
            
            # Validate batch settings
            batch_size = config.get('batch_size', DEFAULT_TASK_CONFIG['batch_size'])
            if batch_size <= 0:
                raise ValidationException(
                    "Invalid batch size",
                    {"size": batch_size}
                )
            
            return True
            
        except Exception as e:
            self._logger.error("Configuration validation failed: %s", str(e))
            raise ValidationException(
                "OCR task configuration validation failed",
                {"error": str(e)}
            )

    async def _validate_file_exists(self, file_path: str) -> bool:
        """Helper method to validate file existence."""
        try:
            from pathlib import Path
            return Path(file_path).is_file()
        except Exception:
            return False

    async def process(self, task_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process OCR task with quality validation and monitoring.
        
        Args:
            task_id: Unique task identifier
            config: Task configuration parameters
            
        Returns:
            Dict[str, Any]: Processing results with quality metrics
            
        Raises:
            TaskException: If processing fails
            ValidationException: If quality validation fails
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            self._logger.info("Starting OCR task processing for task %s", task_id)
            
            # Validate task configuration
            if not await self.validate_config(config):
                raise ValidationException(
                    "Invalid task configuration",
                    {"task_id": task_id}
                )
            
            # Initialize resource tracking
            import psutil
            initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            
            # Process document with quality checks
            processor = await self.get_processor("ocr")
            result = await processor.process({
                "id": task_id,
                **config,
                "quality_threshold": config.get('quality_threshold', 
                                             DEFAULT_TASK_CONFIG['quality_threshold'])
            })
            
            # Validate results against threshold
            quality_score = result.get('metadata', {}).get('quality_score', 0)
            if quality_score < config.get('quality_threshold', 
                                        DEFAULT_TASK_CONFIG['quality_threshold']):
                raise ValidationException(
                    "OCR quality below threshold",
                    {
                        "score": quality_score,
                        "threshold": config['quality_threshold']
                    }
                )
            
            # Track resource usage
            final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            memory_used = final_memory - initial_memory
            
            # Update performance metrics
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(processing_time, quality_score, memory_used)
            
            self._logger.info(
                "OCR task completed for %s in %.2fs with quality score %.2f",
                task_id, processing_time, quality_score
            )
            
            return {
                'status': 'completed',
                'result': result['result'],
                'metadata': {
                    'quality_score': quality_score,
                    'processing_time': processing_time,
                    'memory_usage_mb': memory_used,
                    'performance_metrics': self._metrics
                }
            }
            
        except Exception as e:
            self._logger.error("OCR task processing failed for %s: %s", 
                             task_id, str(e))
            self._metrics['failed_tasks'] += 1
            raise TaskException(
                "OCR task processing failed",
                task_id,
                {"error": str(e)}
            )

    def _update_metrics(self, processing_time: float, quality_score: float,
                       memory_used: float) -> None:
        """Update task performance metrics."""
        self._metrics['processed_tasks'] += 1
        self._metrics['successful_tasks'] += 1
        
        # Update average processing time
        total_tasks = self._metrics['processed_tasks']
        current_avg = self._metrics['avg_processing_time']
        self._metrics['avg_processing_time'] = (
            (current_avg * (total_tasks - 1) + processing_time) / total_tasks
        )
        
        # Update quality scores
        self._metrics['quality_scores'].append(quality_score)
        
        # Update resource usage
        self._metrics['resource_usage']['peak_memory_mb'] = max(
            self._metrics['resource_usage']['peak_memory_mb'],
            memory_used
        )
        self._metrics['resource_usage']['avg_memory_mb'] = (
            (self._metrics['resource_usage']['avg_memory_mb'] * (total_tasks - 1) + 
             memory_used) / total_tasks
        )

class OCRTaskExecutor(BaseTaskExecutor):
    """
    Enhanced executor for OCR tasks with monitoring and error handling.
    
    Extends BaseTaskExecutor with OCR-specific execution capabilities
    including quality validation and resource monitoring.
    """
    
    def __init__(self, task_handler: OCRTask) -> None:
        """
        Initialize OCR task executor with monitoring.
        
        Args:
            task_handler: OCR task handler instance
        """
        super().__init__(task_handler)
        self._task_handler = task_handler
        
        # Initialize execution metrics
        self._execution_metrics = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'retry_count': 0,
            'avg_execution_time': 0.0
        }

    async def execute_async(self, task_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously execute OCR task with monitoring.
        
        Args:
            task_id: Unique task identifier
            config: Task configuration parameters
            
        Returns:
            Dict[str, Any]: Execution results with metrics
            
        Raises:
            TaskException: If execution fails
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            self._logger.info("Starting async OCR execution for task %s", task_id)
            
            # Create execution record
            execution = await self._create_execution_record(task_id)
            
            # Initialize monitoring
            import psutil
            initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            
            # Process task with timeout handling
            timeout = config.get('timeout_seconds', DEFAULT_TASK_CONFIG['timeout_seconds'])
            async with asyncio.timeout(timeout):
                result = await self._task_handler.process(task_id, config)
            
            # Track resource usage
            final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            memory_used = final_memory - initial_memory
            
            # Validate results quality
            quality_score = result.get('metadata', {}).get('quality_score', 0)
            if quality_score < config.get('quality_threshold', 
                                        DEFAULT_TASK_CONFIG['quality_threshold']):
                raise ValidationException(
                    "Execution results below quality threshold",
                    {
                        "score": quality_score,
                        "threshold": config['quality_threshold']
                    }
                )
            
            # Update execution metrics
            execution_time = asyncio.get_event_loop().time() - start_time
            self._update_execution_metrics(execution_time, True)
            
            self._logger.info(
                "Async OCR execution completed for %s in %.2fs",
                task_id, execution_time
            )
            
            return {
                'status': 'completed',
                'execution_id': str(execution.id),
                'result': result['result'],
                'metadata': {
                    **result['metadata'],
                    'execution_time': execution_time,
                    'memory_usage_mb': memory_used,
                    'execution_metrics': self._execution_metrics
                }
            }
            
        except asyncio.TimeoutError:
            self._logger.error("OCR execution timeout for task %s", task_id)
            self._update_execution_metrics(timeout, False)
            raise TaskException(
                "OCR execution timeout",
                task_id,
                {"timeout_seconds": timeout}
            )
            
        except Exception as e:
            self._logger.error("OCR execution failed for task %s: %s", 
                             task_id, str(e))
            execution_time = asyncio.get_event_loop().time() - start_time
            self._update_execution_metrics(execution_time, False)
            raise TaskException(
                "OCR execution failed",
                task_id,
                {"error": str(e)}
            )

    def _update_execution_metrics(self, execution_time: float, success: bool) -> None:
        """Update execution performance metrics."""
        self._execution_metrics['total_executions'] += 1
        if success:
            self._execution_metrics['successful_executions'] += 1
        else:
            self._execution_metrics['failed_executions'] += 1
        
        # Update average execution time
        total = self._execution_metrics['total_executions']
        current_avg = self._execution_metrics['avg_execution_time']
        self._execution_metrics['avg_execution_time'] = (
            (current_avg * (total - 1) + execution_time) / total
        )

__all__ = ['OCRTask', 'OCRTaskExecutor', 'DEFAULT_TASK_CONFIG']