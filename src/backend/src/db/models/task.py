"""
Firestore database model for tasks in the data processing pipeline.

This module implements the database-specific Task model with enhanced validation,
error handling, and performance optimizations for Firestore operations.

Version: 1.0.0
"""

from dataclasses import dataclass  # version: 3.11+
from datetime import datetime  # version: 3.11+
from typing import Dict, Any, Optional, List  # version: 3.11+
from uuid import UUID  # version: 3.11+

import structlog  # version: 23.1+
from pydantic import ValidationError  # version: 2.0+

from core.models import Task
from core.types import TaskType, TaskStatus, TaskConfig
from db.repositories.base import BaseRepository

# Collection name for Firestore
COLLECTION_NAME: str = "tasks"

# Configure structured logger
LOGGER = structlog.get_logger(__name__)

# Define indexes for Firestore queries
TASK_INDEXES = [
    ('type', 'status'),  # For filtering tasks by type and status
    ('created_at',),     # For time-based queries
    ('scheduled_at',)    # For scheduling queries
]

@dataclass
class TaskModel:
    """
    Firestore database model for tasks with enhanced validation and error handling.
    
    Attributes:
        id (str): Task UUID converted to string for Firestore compatibility
        type (TaskType): Type of task (scrape or ocr)
        status (TaskStatus): Current task status
        configuration (TaskConfig): Task-specific configuration
        created_at (datetime): Task creation timestamp
        updated_at (Optional[datetime]): Last update timestamp
        scheduled_at (Optional[datetime]): Scheduled execution time
        execution_history (List[str]): List of execution IDs
        _cache (Dict[str, Any]): Cache for Firestore document data
    """
    
    id: str
    type: TaskType
    status: TaskStatus
    configuration: TaskConfig
    created_at: datetime
    updated_at: Optional[datetime]
    scheduled_at: Optional[datetime]
    execution_history: List[str]
    _cache: Dict[str, Any]

    def __init__(self, task: Task, cache: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize task model from core Task instance.
        
        Args:
            task: Core Task model instance
            cache: Optional Firestore document cache
            
        Raises:
            ValidationError: If task data is invalid
        """
        self.id = str(task.id)
        self.type = task.type
        self.status = task.status
        self.configuration = task.configuration
        self.created_at = task.created_at
        self.updated_at = task.updated_at
        self.scheduled_at = task.scheduled_at
        self.execution_history = [str(x) for x in task.execution_history]
        self._cache = cache or {}

        LOGGER.debug(
            "Created task model",
            task_id=self.id,
            task_type=self.type,
            status=self.status
        )

    def validate(self) -> bool:
        """
        Validate task data against schema requirements.
        
        Returns:
            bool: True if validation passes
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            if not all([self.id, self.type, self.status, self.configuration]):
                raise ValidationError("Missing required fields")

            # Validate field types
            if not isinstance(self.type, str) or self.type not in ['scrape', 'ocr']:
                raise ValidationError(f"Invalid task type: {self.type}")
            
            if not isinstance(self.status, str) or self.status not in [
                'pending', 'running', 'completed', 'failed', 'cancelled'
            ]:
                raise ValidationError(f"Invalid task status: {self.status}")

            # Validate configuration
            if not isinstance(self.configuration, dict):
                raise ValidationError("Configuration must be a dictionary")
            
            if 'source' not in self.configuration:
                raise ValidationError("Configuration must include 'source'")

            return True

        except ValidationError as e:
            LOGGER.error(
                "Task validation failed",
                task_id=self.id,
                error=str(e)
            )
            raise

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task model to dictionary for storage.
        
        Returns:
            Dict[str, Any]: Dictionary representation of task
            
        Raises:
            ValidationError: If task data is invalid
        """
        self.validate()
        
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status,
            'configuration': self.configuration,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'scheduled_at': self.scheduled_at,
            'execution_history': self.execution_history
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskModel':
        """
        Create task model from dictionary data.
        
        Args:
            data: Dictionary containing task data
            
        Returns:
            TaskModel: New task model instance
            
        Raises:
            ValidationError: If data is invalid
        """
        try:
            # Convert timestamps from Firestore
            for field in ['created_at', 'updated_at', 'scheduled_at']:
                if data.get(field):
                    data[field] = data[field].timestamp() \
                        if isinstance(data[field], datetime) \
                        else datetime.fromtimestamp(data[field])

            # Create core Task instance
            task = Task(
                id=UUID(data['id']),
                type=data['type'],
                status=data['status'],
                configuration=data['configuration'],
                created_at=data['created_at'],
                updated_at=data.get('updated_at'),
                scheduled_at=data.get('scheduled_at'),
                execution_history=[UUID(x) for x in data.get('execution_history', [])]
            )

            return cls(task=task, cache=data)

        except (ValueError, KeyError) as e:
            LOGGER.error(
                "Failed to create task from dictionary",
                error=str(e),
                data=data
            )
            raise ValidationError("Invalid task data") from e

    def to_firestore(self) -> Dict[str, Any]:
        """
        Convert task to Firestore-compatible format.
        
        Returns:
            Dict[str, Any]: Firestore document data
            
        Raises:
            ValidationError: If conversion fails
        """
        try:
            data = self.to_dict()
            
            # Add Firestore metadata
            data['_collection'] = COLLECTION_NAME
            data['_updated_at'] = datetime.utcnow()
            
            # Add indexing hints
            data['_searchable'] = {
                'type_status': f"{self.type}_{self.status}",
                'created_date': self.created_at.date().isoformat()
            }
            
            LOGGER.debug(
                "Converted task to Firestore format",
                task_id=self.id
            )
            
            return data

        except Exception as e:
            LOGGER.error(
                "Failed to convert task to Firestore format",
                task_id=self.id,
                error=str(e)
            )
            raise

    @classmethod
    def from_firestore(cls, doc: Dict[str, Any]) -> 'TaskModel':
        """
        Create task model from Firestore document.
        
        Args:
            doc: Firestore document data
            
        Returns:
            TaskModel: New task model instance
            
        Raises:
            ValidationError: If document data is invalid
        """
        try:
            # Remove Firestore metadata
            data = {k: v for k, v in doc.items() if not k.startswith('_')}
            
            LOGGER.debug(
                "Creating task from Firestore document",
                doc_id=doc.get('id')
            )
            
            return cls.from_dict(data)

        except Exception as e:
            LOGGER.error(
                "Failed to create task from Firestore document",
                doc_id=doc.get('id'),
                error=str(e)
            )
            raise ValidationError("Invalid Firestore document") from e