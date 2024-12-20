"""
Firestore database model for task executions in the data processing pipeline.

This module provides the database-specific implementation of the TaskExecution model,
handling persistence and retrieval of task execution data in Cloud Firestore.

Version: 1.0.0
"""

from dataclasses import dataclass  # version: 3.11+
from datetime import datetime  # version: 3.11+
from typing import Dict, Any, Optional, List  # version: 3.11+

from core.models import TaskExecution
from core.types import TaskStatus, TaskResult, TaskID, ExecutionID, DataObjectID

# Firestore collection name for task executions
COLLECTION_NAME = "task_executions"

@dataclass
class TaskExecutionModel:
    """
    Firestore database model for task executions, extending the core TaskExecution model
    with database-specific functionality for persistence and retrieval.

    Attributes:
        id (str): Unique identifier for the execution (UUID as string)
        task_id (str): ID of the associated task (UUID as string)
        status (TaskStatus): Current execution status
        start_time (datetime): When execution started
        end_time (Optional[datetime]): When execution completed
        result (Optional[Dict[str, Any]]): Execution results if completed
        error_message (Optional[str]): Error details if failed
        output_objects (List[str]): List of generated data object IDs
    """

    id: str
    task_id: str
    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    output_objects: List[str]

    def __init__(self, execution: TaskExecution) -> None:
        """
        Initialize a new task execution model from a core TaskExecution instance.

        Args:
            execution: Core TaskExecution model to convert to database model
        """
        self.id = str(execution.id)
        self.task_id = str(execution.task_id)
        self.status = execution.status
        self.start_time = execution.start_time
        self.end_time = execution.end_time
        self.result = execution.result
        self.error_message = execution.error_message
        self.output_objects = [str(obj_id) for obj_id in execution.output_objects]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the task execution model to a dictionary for Firestore storage.

        Returns:
            Dict[str, Any]: Dictionary representation of task execution suitable for Firestore
        """
        return {
            "id": self.id,
            "task_id": self.task_id,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "result": self.result,
            "error_message": self.error_message,
            "output_objects": self.output_objects
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskExecutionModel":
        """
        Create a task execution model instance from a Firestore document dictionary.

        Args:
            data: Dictionary containing task execution data from Firestore

        Returns:
            TaskExecutionModel: New task execution model instance
        """
        # Convert Firestore Timestamp objects to datetime if present
        start_time = data["start_time"]
        if hasattr(start_time, "timestamp"):
            start_time = datetime.fromtimestamp(start_time.timestamp())

        end_time = data.get("end_time")
        if end_time and hasattr(end_time, "timestamp"):
            end_time = datetime.fromtimestamp(end_time.timestamp())

        # Create a new model instance with converted data
        model = cls.__new__(cls)
        model.id = data["id"]
        model.task_id = data["task_id"]
        model.status = data["status"]
        model.start_time = start_time
        model.end_time = end_time
        model.result = data.get("result")
        model.error_message = data.get("error_message")
        model.output_objects = data.get("output_objects", [])
        return model

    def add_output_object(self, object_id: DataObjectID) -> None:
        """
        Add a data object ID to the execution's output objects list.

        Args:
            object_id: UUID of the data object to add
        """
        str_id = str(object_id)
        if str_id not in self.output_objects:
            self.output_objects.append(str_id)