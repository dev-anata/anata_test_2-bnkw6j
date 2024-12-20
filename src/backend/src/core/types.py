"""
Core type definitions and type aliases for the data processing pipeline.

This module provides standardized type definitions used across the application to ensure
type safety and consistent data modeling. It defines the core types for tasks, executions,
data objects and their associated metadata.

Version: 1.0.0
"""

from typing import Literal, TypeAlias, Dict, List, Optional, Union, Any  # version: 3.11+
from uuid import UUID  # version: 3.11+
from datetime import datetime  # version: 3.11+

# Task-related type definitions
TaskType = Literal['scrape', 'ocr']
TaskStatus = Literal['pending', 'running', 'completed', 'failed', 'cancelled']

# Unique identifier type aliases
TaskID = UUID
DataSourceID = UUID
ExecutionID = UUID
DataObjectID = UUID

# Configuration and result type definitions
TaskConfig = TypeAlias = Dict[str, Union[str, Dict[str, Any]]]
"""Type alias for task configuration structure.

Attributes:
    source (str): The source identifier or URL for the task
    parameters (Dict[str, Any]): Additional parameters specific to the task type
"""

TaskResult = TypeAlias = Dict[str, Union[str, Dict[str, Any], None]]
"""Type alias for task execution results.

Attributes:
    status (str): The final status of the task execution
    data (Dict[str, Any]): The processed data or results
    error (Optional[str]): Error message if the task failed, None otherwise
"""

Metadata = TypeAlias = Dict[str, Union[str, datetime, Dict[str, Any]]]
"""Type alias for data object metadata.

Attributes:
    content_type (str): The MIME type of the data object
    source (str): The origin or source of the data
    timestamp (datetime): When the data was created/processed
    attributes (Dict[str, Any]): Additional metadata attributes
"""

# Structured type definitions for static typing
TaskConfigDict = Dict[str, Any]
"""Detailed structure for task configuration."""

TaskResultDict = Dict[str, Union[str, Dict[str, Any], None]]
"""Detailed structure for task execution results."""

MetadataDict = Dict[str, Union[str, datetime, Dict[str, Any]]]
"""Detailed structure for object metadata."""

# Type aliases for complex data structures
TaskList = List[Dict[str, Union[TaskID, TaskType, TaskStatus, datetime]]]
"""Type alias for list of task summaries."""

ExecutionList = List[Dict[str, Union[ExecutionID, TaskID, TaskStatus, datetime]]]
"""Type alias for list of task executions."""

DataObjectList = List[Dict[str, Union[DataObjectID, ExecutionID, str, Metadata]]]
"""Type alias for list of data objects."""

__all__ = [
    'TaskType',
    'TaskStatus',
    'TaskID',
    'DataSourceID',
    'ExecutionID',
    'DataObjectID',
    'TaskConfig',
    'TaskResult',
    'Metadata',
    'TaskConfigDict',
    'TaskResultDict',
    'MetadataDict',
    'TaskList',
    'ExecutionList',
    'DataObjectList'
]