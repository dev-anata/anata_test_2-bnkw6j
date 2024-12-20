"""
Core exception classes for the data processing pipeline.

This module defines a comprehensive hierarchy of custom exceptions used throughout
the application to provide standardized error handling and consistent error reporting.
Each exception type is designed to capture specific error scenarios and relevant context
for proper error handling and debugging.

Version: 1.0.0
"""

from typing import Dict, Optional, Any  # version: 3.11+
from core.types import TaskType, TaskStatus  # Internal import


class PipelineException(Exception):
    """
    Base exception class for all pipeline-specific exceptions.
    
    Provides a foundation for standardized error handling across the application
    with support for detailed error context.
    
    Attributes:
        message (str): Human-readable error description
        details (Optional[Dict[str, Any]]): Additional error context and metadata
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the base pipeline exception.
        
        Args:
            message: Human-readable error description
            details: Optional dictionary containing additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationException(PipelineException):
    """
    Exception raised for validation errors in input data or configuration.
    
    Used when input validation fails, including schema validation, data type validation,
    and business rule validation.
    
    Attributes:
        message (str): Human-readable validation error description
        validation_errors (Dict[str, Any]): Detailed validation error information
    """
    
    def __init__(self, message: str, validation_errors: Dict[str, Any]) -> None:
        """
        Initialize validation exception with specific validation error details.
        
        Args:
            message: Human-readable validation error description
            validation_errors: Dictionary containing validation error details
        """
        super().__init__(message, details={"validation_errors": validation_errors})
        self.validation_errors = validation_errors


class TaskException(PipelineException):
    """
    Exception raised for task-related errors during execution or scheduling.
    
    Used for errors that occur during task processing, including execution failures,
    scheduling conflicts, and task state transitions.
    
    Attributes:
        message (str): Human-readable task error description
        task_id (str): Identifier of the task that encountered the error
        task_details (Optional[Dict[str, Any]]): Additional task-specific context
    """
    
    def __init__(self, message: str, task_id: str, 
                 task_details: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize task exception with task-specific context.
        
        Args:
            message: Human-readable task error description
            task_id: Identifier of the affected task
            task_details: Optional dictionary containing task-specific context
        """
        super().__init__(message, details={
            "task_id": task_id,
            "task_details": task_details or {}
        })
        self.task_id = task_id
        self.task_details = task_details or {}


class StorageException(PipelineException):
    """
    Exception raised for storage-related errors (GCS, local storage).
    
    Used for errors that occur during storage operations, including read/write failures,
    permission issues, and storage quota exceeded scenarios.
    
    Attributes:
        message (str): Human-readable storage error description
        storage_path (str): Path where the storage operation failed
        storage_details (Optional[Dict[str, Any]]): Additional storage context
    """
    
    def __init__(self, message: str, storage_path: str,
                 storage_details: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize storage exception with storage-specific context.
        
        Args:
            message: Human-readable storage error description
            storage_path: Path where the storage operation failed
            storage_details: Optional dictionary containing storage-specific context
        """
        super().__init__(message, details={
            "storage_path": storage_path,
            "storage_details": storage_details or {}
        })
        self.storage_path = storage_path
        self.storage_details = storage_details or {}


class ConfigurationException(PipelineException):
    """
    Exception raised for configuration-related errors.
    
    Used for errors related to system configuration, including invalid configuration
    values, missing required configuration, and configuration conflicts.
    
    Attributes:
        message (str): Human-readable configuration error description
        config_details (Optional[Dict[str, Any]]): Additional configuration context
    """
    
    def __init__(self, message: str,
                 config_details: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize configuration exception with configuration-specific context.
        
        Args:
            message: Human-readable configuration error description
            config_details: Optional dictionary containing configuration context
        """
        super().__init__(message, details={"config_details": config_details or {}})
        self.config_details = config_details or {}


__all__ = [
    'PipelineException',
    'ValidationException',
    'TaskException',
    'StorageException',
    'ConfigurationException'
]