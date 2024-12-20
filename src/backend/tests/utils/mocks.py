"""
Mock implementations for testing core services and repositories.

This module provides test doubles that simulate the behavior of real components
while allowing controlled testing scenarios and error simulation. It includes
mock implementations of repositories and services with configurable error triggers.

Version: 1.0.0
"""

from unittest.mock import MagicMock, Mock, patch  # version: 3.11+
from typing import Dict, List, Optional, TypeVar  # version: 3.11+
from datetime import datetime  # version: 3.11+
from uuid import UUID, uuid4  # version: 3.11+

from core.models import Task, TaskExecution, DataObject
from core.types import TaskType, TaskStatus, TaskConfig, TaskResult
from db.repositories.base import BaseRepository

# Type variable for generic repository operations
T = TypeVar('T')

class MockTaskRepository(BaseRepository[Task]):
    """
    Mock implementation of task repository for testing with error simulation.
    
    Provides in-memory storage and configurable error triggers for testing
    different scenarios and error handling.
    """
    
    def __init__(self) -> None:
        """Initialize mock repository with empty storage and error triggers."""
        self._tasks: Dict[UUID, Task] = {}
        self._error_triggers: Dict[str, Exception] = {}
        
        # Set up default error scenarios
        self._error_triggers = {
            'storage_error': StorageException('Mock storage error'),
            'validation_error': ValidationException('Mock validation error'),
            'not_found': KeyError('Task not found')
        }

    async def create(self, task: Task) -> Task:
        """
        Mock task creation with error simulation.
        
        Args:
            task: Task instance to create
            
        Returns:
            Created task
            
        Raises:
            Exception: If error trigger is configured
        """
        if 'create' in self._error_triggers:
            raise self._error_triggers['create']
            
        if not isinstance(task, Task):
            raise ValidationException('Invalid task type')
            
        self._tasks[task.id] = task
        return task

    async def get(self, task_id: UUID) -> Optional[Task]:
        """
        Mock task retrieval with error simulation.
        
        Args:
            task_id: UUID of task to retrieve
            
        Returns:
            Task if found, None otherwise
            
        Raises:
            Exception: If error trigger is configured
        """
        if 'get' in self._error_triggers:
            raise self._error_triggers['get']
            
        return self._tasks.get(task_id)

    async def update(self, task: Task) -> Task:
        """
        Mock task update with error simulation.
        
        Args:
            task: Task instance to update
            
        Returns:
            Updated task
            
        Raises:
            Exception: If error trigger is configured or task not found
        """
        if 'update' in self._error_triggers:
            raise self._error_triggers['update']
            
        if task.id not in self._tasks:
            raise KeyError(f'Task {task.id} not found')
            
        self._tasks[task.id] = task
        return task

    def set_error_trigger(self, operation: str, error: Exception) -> None:
        """
        Configure error trigger for testing.
        
        Args:
            operation: Operation to trigger error for ('create', 'get', 'update')
            error: Exception to raise when triggered
        """
        self._error_triggers[operation] = error


class MockTaskService:
    """
    Mock implementation of task service for testing with processor simulation.
    
    Provides mock task processing capabilities with configurable behaviors
    and status tracking.
    """
    
    def __init__(self) -> None:
        """Initialize mock service with dependencies."""
        self._repository = MockTaskRepository()
        self._processors: Dict[TaskType, Mock] = {}
        self._task_statuses: Dict[UUID, TaskStatus] = {}
        
        # Set up default processors
        self._processors = {
            'scrape': Mock(return_value={'status': 'completed'}),
            'ocr': Mock(return_value={'status': 'completed'})
        }

    async def create_task(
        self,
        task_type: TaskType,
        config: TaskConfig,
        scheduled_at: Optional[datetime] = None
    ) -> UUID:
        """
        Mock task creation with processor assignment.
        
        Args:
            task_type: Type of task to create
            config: Task configuration
            scheduled_at: Optional scheduled execution time
            
        Returns:
            Created task ID
        """
        task = create_mock_task(task_type, config, status='pending')
        if scheduled_at:
            task.scheduled_at = scheduled_at
            
        await self._repository.create(task)
        self._task_statuses[task.id] = 'pending'
        return task.id

    async def get_task_status(self, task_id: UUID) -> TaskStatus:
        """
        Mock task status retrieval.
        
        Args:
            task_id: UUID of task to check
            
        Returns:
            Current task status
            
        Raises:
            KeyError: If task not found
        """
        if task_id not in self._task_statuses:
            raise KeyError(f'Task {task_id} not found')
        return self._task_statuses[task_id]

    def register_processor(self, task_type: TaskType, processor: Mock) -> None:
        """
        Register mock processor for task type.
        
        Args:
            task_type: Type of task to register processor for
            processor: Mock processor implementation
        """
        self._processors[task_type] = processor


def create_mock_task(
    task_type: TaskType,
    config: TaskConfig,
    status: Optional[TaskStatus] = None
) -> Task:
    """
    Helper function to create mock task instances with realistic data.
    
    Args:
        task_type: Type of task to create
        config: Task configuration
        status: Optional initial status
        
    Returns:
        Configured mock task instance
    """
    return Task(
        id=uuid4(),
        type=task_type,
        status=status or 'pending',
        configuration=config,
        created_at=datetime.utcnow(),
        updated_at=None,
        scheduled_at=None,
        execution_history=[]
    )


def create_mock_execution(
    task_id: UUID,
    status: Optional[TaskStatus] = None,
    result: Optional[TaskResult] = None
) -> TaskExecution:
    """
    Helper function to create mock task execution instances.
    
    Args:
        task_id: ID of associated task
        status: Optional execution status
        result: Optional execution result
        
    Returns:
        Configured mock execution instance
    """
    return TaskExecution(
        id=uuid4(),
        task_id=task_id,
        status=status or 'running',
        start_time=datetime.utcnow(),
        end_time=None,
        result=result,
        error_message=None,
        output_objects=[]
    )

__all__ = [
    'MockTaskRepository',
    'MockTaskService',
    'create_mock_task',
    'create_mock_execution'
]