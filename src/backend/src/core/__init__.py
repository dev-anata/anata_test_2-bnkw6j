"""
Core module initialization file for the Data Processing Pipeline.

This module provides a clean public API by exposing essential types, interfaces,
and models used throughout the system. It serves as the main entry point for
accessing core functionality and ensures consistent usage of data structures
and interfaces across the application.

Version: 1.0.0
"""

# Import core type definitions
from core.types import (
    TaskType,
    TaskStatus,
    TaskConfig,
    TaskResult,
    TaskID,
    ExecutionID,
    DataObjectID,
    DataSourceID,
    Metadata
)

# Import core interfaces
from core.interfaces import (
    TaskProcessor,
    TaskScheduler,
    TaskExecutor,
    StorageManager
)

# Import core models
from core.models import (
    Task,
    TaskExecution,
    DataObject
)

# Import core exceptions
from core.exceptions import (
    PipelineException,
    ValidationException,
    TaskException,
    StorageException,
    ConfigurationException
)

# Package version
__version__ = '1.0.0'

# Public API
__all__ = [
    # Core Types
    'TaskType',
    'TaskStatus',
    'TaskConfig',
    'TaskResult',
    'TaskID',
    'ExecutionID',
    'DataObjectID',
    'DataSourceID',
    'Metadata',
    
    # Core Interfaces
    'TaskProcessor',
    'TaskScheduler',
    'TaskExecutor',
    'StorageManager',
    
    # Core Models
    'Task',
    'TaskExecution',
    'DataObject',
    
    # Core Exceptions
    'PipelineException',
    'ValidationException',
    'TaskException',
    'StorageException',
    'ConfigurationException',
    
    # Package Metadata
    '__version__'
]

# Type checking and documentation hints
TaskType.__doc__ = "Literal type specifying valid task types: 'scrape' or 'ocr'"
TaskStatus.__doc__ = """Literal type specifying valid task statuses:
'pending', 'running', 'completed', 'failed', or 'cancelled'"""