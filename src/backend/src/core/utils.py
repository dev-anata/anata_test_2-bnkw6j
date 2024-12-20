"""
Core utility functions for the data processing pipeline.

This module provides essential utility functions for data processing, validation,
error handling, and type conversion across the pipeline. It implements robust
error handling, performance monitoring, and standardized data manipulation.

Version: 1.0.0
"""

from datetime import datetime, timedelta  # version: 3.11+
from uuid import uuid4, UUID  # version: 3.11+
from typing import Dict, List, Optional, Any, Union, Type, Callable  # version: 3.11+
from types import TracebackType
import json  # version: 3.11+
import time
import logging
from threading import Lock

from core.types import TaskType, TaskStatus, TaskConfig, TaskResult
from core.exceptions import ValidationException, TaskException

# Global constants
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
MAX_BATCH_SIZE = 100

# Configure logging
logger = logging.getLogger(__name__)

def validate_task_config(config: TaskConfig) -> bool:
    """
    Validates task configuration against schema with comprehensive type checking.
    
    Args:
        config: Task configuration dictionary to validate
        
    Returns:
        bool: True if configuration is valid
        
    Raises:
        ValidationException: If configuration is invalid with detailed error context
    """
    try:
        # Required fields validation
        required_fields = {'type', 'source', 'parameters'}
        missing_fields = required_fields - set(config.keys())
        if missing_fields:
            raise ValidationException(
                f"Missing required fields: {missing_fields}",
                {"missing_fields": list(missing_fields)}
            )

        # Type validation
        if not isinstance(config.get('type'), str) or config['type'] not in TaskType.__args__:
            raise ValidationException(
                f"Invalid task type: {config.get('type')}",
                {"valid_types": list(TaskType.__args__)}
            )

        # Source validation
        if not isinstance(config.get('source'), str) or not config['source'].strip():
            raise ValidationException(
                "Invalid source specification",
                {"source": config.get('source')}
            )

        # Parameters validation
        if not isinstance(config.get('parameters'), dict):
            raise ValidationException(
                "Parameters must be a dictionary",
                {"parameters": config.get('parameters')}
            )

        # Task-specific validation
        if config['type'] == 'scrape':
            _validate_scrape_config(config['parameters'])
        elif config['type'] == 'ocr':
            _validate_ocr_config(config['parameters'])

        return True

    except ValidationException:
        raise
    except Exception as e:
        raise ValidationException(
            f"Configuration validation failed: {str(e)}",
            {"error": str(e)}
        )

def retry_operation(
    operation: Callable,
    max_attempts: Optional[int] = RETRY_ATTEMPTS,
    delay_seconds: Optional[float] = RETRY_DELAY_SECONDS
) -> Any:
    """
    Executes an operation with exponential backoff retry mechanism.
    
    Args:
        operation: Callable to execute
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries in seconds
        
    Returns:
        Any: Result of the operation
        
    Raises:
        TaskException: If all retry attempts fail
    """
    attempts = 0
    last_exception = None
    
    while attempts < max_attempts:
        try:
            return operation()
        except Exception as e:
            attempts += 1
            last_exception = e
            
            if attempts == max_attempts:
                break
                
            wait_time = delay_seconds * (2 ** (attempts - 1))  # Exponential backoff
            logger.warning(
                f"Operation failed (attempt {attempts}/{max_attempts}). "
                f"Retrying in {wait_time} seconds.",
                extra={
                    "attempt": attempts,
                    "max_attempts": max_attempts,
                    "delay": wait_time,
                    "error": str(e)
                }
            )
            time.sleep(wait_time)
    
    raise TaskException(
        f"Operation failed after {max_attempts} attempts",
        str(uuid4()),
        {"last_error": str(last_exception)}
    )

def generate_task_id() -> UUID:
    """
    Generates a unique task identifier with validation.
    
    Returns:
        UUID: Unique task identifier
        
    Raises:
        ValidationException: If UUID generation fails
    """
    try:
        return uuid4()
    except Exception as e:
        raise ValidationException(
            "Failed to generate task ID",
            {"error": str(e)}
        )

def format_timestamp(timestamp: datetime) -> str:
    """
    Formats datetime object to ISO 8601 string with timezone handling.
    
    Args:
        timestamp: Datetime object to format
        
    Returns:
        str: ISO 8601 formatted timestamp string
        
    Raises:
        ValidationException: If timestamp formatting fails
    """
    try:
        if timestamp.tzinfo is None:
            timestamp = timestamp.astimezone()
        return timestamp.isoformat()
    except Exception as e:
        raise ValidationException(
            "Failed to format timestamp",
            {"error": str(e)}
        )

def batch_items(items: List[Any], batch_size: Optional[int] = MAX_BATCH_SIZE) -> List[List[Any]]:
    """
    Splits a list of items into optimized batches with memory efficiency.
    
    Args:
        items: List of items to batch
        batch_size: Maximum size of each batch
        
    Returns:
        List[List[Any]]: List of batches
        
    Raises:
        ValidationException: If batching parameters are invalid
    """
    if not isinstance(items, list):
        raise ValidationException(
            "Items must be a list",
            {"type": type(items).__name__}
        )
        
    if batch_size is not None and (not isinstance(batch_size, int) or batch_size <= 0):
        raise ValidationException(
            "Batch size must be a positive integer",
            {"batch_size": batch_size}
        )
        
    batch_size = min(batch_size or MAX_BATCH_SIZE, len(items))
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

class TaskTimer:
    """
    Thread-safe context manager for tracking and logging task execution time.
    
    Attributes:
        task_id (str): Unique identifier for the task
        start_time (datetime): Task start timestamp
        end_time (Optional[datetime]): Task end timestamp
        metrics (Dict[str, Any]): Performance metrics collection
    """
    
    def __init__(self, task_id: str) -> None:
        """
        Initialize timer with task ID and prepare metrics collection.
        
        Args:
            task_id: Unique identifier for the task
        """
        self.task_id = task_id
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.metrics: Dict[str, Any] = {}
        self._lock = Lock()

    def __enter__(self) -> 'TaskTimer':
        """
        Enter context manager and start performance tracking.
        
        Returns:
            TaskTimer: Self reference
        """
        with self._lock:
            self.start_time = datetime.now()
            self.metrics = {
                'task_id': self.task_id,
                'start_time': format_timestamp(self.start_time)
            }
            logger.info(
                f"Task {self.task_id} started",
                extra={'metrics': self.metrics}
            )
            return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType]
    ) -> None:
        """
        Exit context manager, calculate metrics, and log performance data.
        
        Args:
            exc_type: Exception type if an error occurred
            exc_value: Exception instance if an error occurred
            traceback: Traceback if an error occurred
        """
        with self._lock:
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()
            
            self.metrics.update({
                'end_time': format_timestamp(self.end_time),
                'duration_seconds': duration,
                'status': 'failed' if exc_type else 'completed'
            })
            
            if exc_type:
                self.metrics['error'] = str(exc_value)
                logger.error(
                    f"Task {self.task_id} failed after {duration:.2f} seconds",
                    extra={'metrics': self.metrics},
                    exc_info=(exc_type, exc_value, traceback)
                )
            else:
                logger.info(
                    f"Task {self.task_id} completed in {duration:.2f} seconds",
                    extra={'metrics': self.metrics}
                )

def _validate_scrape_config(parameters: Dict[str, Any]) -> None:
    """
    Validates scraping task specific configuration parameters.
    
    Args:
        parameters: Scraping configuration parameters
        
    Raises:
        ValidationException: If parameters are invalid
    """
    required_params = {'url', 'selectors'}
    missing_params = required_params - set(parameters.keys())
    if missing_params:
        raise ValidationException(
            f"Missing required scraping parameters: {missing_params}",
            {"missing_params": list(missing_params)}
        )

def _validate_ocr_config(parameters: Dict[str, Any]) -> None:
    """
    Validates OCR task specific configuration parameters.
    
    Args:
        parameters: OCR configuration parameters
        
    Raises:
        ValidationException: If parameters are invalid
    """
    required_params = {'file_path', 'language'}
    missing_params = required_params - set(parameters.keys())
    if missing_params:
        raise ValidationException(
            f"Missing required OCR parameters: {missing_params}",
            {"missing_params": list(missing_params)}
        )

__all__ = [
    'validate_task_config',
    'retry_operation',
    'generate_task_id',
    'format_timestamp',
    'batch_items',
    'TaskTimer'
]