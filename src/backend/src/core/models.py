"""
Core data models for the data processing pipeline.

This module defines the fundamental data structures used across the system,
including tasks, executions, and data objects. These models provide a standardized
way to represent and manage data processing operations.

Version: 1.0.0
"""

from dataclasses import dataclass, field  # version: 3.11+
from datetime import datetime  # version: 3.11+
from uuid import UUID, uuid4  # version: 3.11+
from typing import Dict, Optional, List, Any  # version: 3.11+

from core.types import (
    TaskType, TaskStatus, TaskConfig, TaskResult, TaskID,
    ExecutionID, DataObjectID, DataSourceID, Metadata
)
from core.exceptions import ValidationException


@dataclass
class Task:
    """
    Core task model representing a data processing task (scraping or OCR).
    
    This class represents the fundamental unit of work in the pipeline,
    tracking the task's lifecycle from creation through execution.
    
    Attributes:
        id (UUID): Unique identifier for the task
        type (TaskType): Type of task (scrape or ocr)
        status (TaskStatus): Current status of the task
        configuration (TaskConfig): Task-specific configuration
        created_at (datetime): Timestamp when task was created
        updated_at (Optional[datetime]): Timestamp of last update
        scheduled_at (Optional[datetime]): When task is scheduled to run
        execution_history (List[ExecutionID]): List of execution attempts
    """
    
    id: UUID = field(default_factory=uuid4)
    type: TaskType
    status: TaskStatus = field(default="pending")
    configuration: TaskConfig
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    execution_history: List[ExecutionID] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate task configuration after initialization."""
        if not isinstance(self.configuration, dict):
            raise ValidationException(
                "Invalid task configuration format",
                {"expected": "dict", "received": type(self.configuration).__name__}
            )
        
        if "source" not in self.configuration:
            raise ValidationException(
                "Missing required configuration field",
                {"field": "source"}
            )

    def update_status(self, new_status: TaskStatus) -> None:
        """
        Update the task's status and timestamp.
        
        Args:
            new_status: New status to set for the task
            
        Raises:
            ValidationException: If status transition is invalid
        """
        valid_transitions = {
            "pending": ["running", "cancelled"],
            "running": ["completed", "failed"],
            "completed": [],
            "failed": ["pending"],
            "cancelled": ["pending"]
        }
        
        if new_status not in valid_transitions.get(self.status, []):
            raise ValidationException(
                "Invalid status transition",
                {
                    "current_status": self.status,
                    "new_status": new_status,
                    "allowed_transitions": valid_transitions[self.status]
                }
            )
        
        self.status = new_status
        self.updated_at = datetime.utcnow()

    def add_execution(self, execution_id: ExecutionID) -> None:
        """
        Add an execution ID to the task's history.
        
        Args:
            execution_id: UUID of the execution to add
        """
        self.execution_history.append(execution_id)
        self.updated_at = datetime.utcnow()


@dataclass
class TaskExecution:
    """
    Model representing a single execution of a task.
    
    Tracks the execution details, progress, and results of a specific
    task execution attempt.
    
    Attributes:
        id (UUID): Unique identifier for the execution
        task_id (TaskID): ID of the associated task
        status (TaskStatus): Current execution status
        start_time (datetime): When execution started
        end_time (Optional[datetime]): When execution completed
        result (Optional[TaskResult]): Execution results if completed
        error_message (Optional[str]): Error details if failed
        output_objects (List[DataObjectID]): Generated data objects
    """
    
    id: UUID = field(default_factory=uuid4)
    task_id: TaskID
    status: TaskStatus = field(default="running")
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    result: Optional[TaskResult] = None
    error_message: Optional[str] = None
    output_objects: List[DataObjectID] = field(default_factory=list)

    def complete(self, result: TaskResult) -> None:
        """
        Mark the execution as complete with results.
        
        Args:
            result: The execution results to store
            
        Raises:
            ValidationException: If execution is already completed or failed
        """
        if self.status not in ["running"]:
            raise ValidationException(
                "Cannot complete execution with current status",
                {"current_status": self.status}
            )
        
        self.status = "completed"
        self.result = result
        self.end_time = datetime.utcnow()

    def fail(self, error_message: str) -> None:
        """
        Mark the execution as failed with error details.
        
        Args:
            error_message: Description of what went wrong
            
        Raises:
            ValidationException: If execution is already completed or failed
        """
        if self.status not in ["running"]:
            raise ValidationException(
                "Cannot fail execution with current status",
                {"current_status": self.status}
            )
        
        self.status = "failed"
        self.error_message = error_message
        self.end_time = datetime.utcnow()


@dataclass
class DataObject:
    """
    Model representing processed data output (scraped content or OCR result).
    
    Stores metadata and references to processed data stored in the system.
    
    Attributes:
        id (UUID): Unique identifier for the data object
        execution_id (ExecutionID): ID of the execution that created this
        storage_path (str): Path where the data is stored
        content_type (str): MIME type of the stored data
        metadata (Metadata): Additional data attributes
        created_at (datetime): When the object was created
    """
    
    id: UUID = field(default_factory=uuid4)
    execution_id: ExecutionID
    storage_path: str
    content_type: str
    metadata: Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate data object attributes after initialization."""
        if not self.storage_path:
            raise ValidationException(
                "Storage path cannot be empty",
                {"field": "storage_path"}
            )
        
        if not self.content_type:
            raise ValidationException(
                "Content type cannot be empty",
                {"field": "content_type"}
            )
        
        if not isinstance(self.metadata, dict):
            raise ValidationException(
                "Invalid metadata format",
                {"expected": "dict", "received": type(self.metadata).__name__}
            )


__all__ = [
    'Task',
    'TaskExecution',
    'DataObject'
]