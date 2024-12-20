"""
Core interfaces and protocols for the data processing pipeline.

This module defines the fundamental interfaces that different components of the system
must implement, ensuring consistent behavior and interaction across the pipeline.

Version: 1.0.0
"""

from typing import Protocol, runtime_checkable, AsyncContextManager, Dict, List, Optional  # version: 3.11+

from core.types import (
    TaskType, TaskStatus, TaskConfig, TaskResult, TaskID,
    ExecutionID, DataObjectID, Metadata
)
from core.models import Task, TaskExecution, DataObject


@runtime_checkable
class TaskProcessor(Protocol):
    """
    Protocol defining the interface for task processing components (OCR and Scraping).
    
    Implementations must provide the processor_type property and implement the process
    method according to their specific processing logic.
    """
    
    @property
    def processor_type(self) -> TaskType:
        """
        The type of tasks this processor handles.
        
        Returns:
            TaskType: Either 'scrape' or 'ocr'
        """
        ...

    async def process(self, task: Task) -> TaskResult:
        """
        Process a task according to its configuration.
        
        Args:
            task: The task to process, containing configuration and metadata
            
        Returns:
            TaskResult: The results of the processing operation
            
        Raises:
            ValidationException: If task configuration is invalid
            TaskException: If processing fails
            StorageException: If storage operations fail
        """
        ...


@runtime_checkable
class TaskScheduler(Protocol):
    """
    Protocol defining the interface for task scheduling and management.
    
    Implementations handle task scheduling, cancellation, and lifecycle management
    according to the system's scheduling requirements.
    """
    
    async def schedule_task(
        self,
        task_type: TaskType,
        config: TaskConfig,
        scheduled_at: Optional[datetime] = None
    ) -> Task:
        """
        Schedule a new task for execution.
        
        Args:
            task_type: Type of task to schedule (scrape or ocr)
            config: Task-specific configuration
            scheduled_at: Optional timestamp for delayed execution
            
        Returns:
            Task: The created and scheduled task
            
        Raises:
            ValidationException: If configuration is invalid
            ConfigurationException: If scheduling parameters are invalid
        """
        ...

    async def cancel_task(self, task_id: TaskID) -> bool:
        """
        Cancel a scheduled or running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if task was successfully cancelled, False otherwise
            
        Raises:
            TaskException: If task cannot be cancelled or doesn't exist
        """
        ...

    async def get_scheduled_tasks(
        self,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """
        Retrieve scheduled tasks with optional filtering.
        
        Args:
            task_type: Optional filter by task type
            status: Optional filter by task status
            
        Returns:
            List[Task]: List of tasks matching the filter criteria
        """
        ...


@runtime_checkable
class TaskExecutor(Protocol):
    """
    Protocol defining the interface for task execution handling.
    
    Implementations manage the actual execution of tasks, including resource
    allocation, monitoring, and result handling.
    """
    
    async def execute(self, task: Task) -> TaskExecution:
        """
        Execute a scheduled task.
        
        Args:
            task: The task to execute
            
        Returns:
            TaskExecution: Record of the task execution
            
        Raises:
            TaskException: If execution fails
            ValidationException: If task is in invalid state
        """
        ...

    async def get_status(self, execution_id: ExecutionID) -> TaskStatus:
        """
        Get the current status of a task execution.
        
        Args:
            execution_id: ID of the execution to check
            
        Returns:
            TaskStatus: Current status of the execution
            
        Raises:
            TaskException: If execution record not found
        """
        ...

    async def get_result(self, execution_id: ExecutionID) -> Optional[TaskResult]:
        """
        Retrieve the results of a task execution.
        
        Args:
            execution_id: ID of the execution
            
        Returns:
            Optional[TaskResult]: Execution results if available, None otherwise
            
        Raises:
            TaskException: If execution record not found
        """
        ...

    async def list_executions(
        self,
        task_id: Optional[TaskID] = None,
        status: Optional[TaskStatus] = None
    ) -> List[TaskExecution]:
        """
        List task executions with optional filtering.
        
        Args:
            task_id: Optional filter by task ID
            status: Optional filter by execution status
            
        Returns:
            List[TaskExecution]: List of executions matching the filter criteria
        """
        ...


@runtime_checkable
class StorageManager(Protocol):
    """
    Protocol defining the interface for data storage operations.
    
    Implementations handle the storage and retrieval of processed data and
    associated metadata.
    """
    
    async def store_data(
        self,
        execution_id: ExecutionID,
        data: bytes,
        content_type: str,
        metadata: Metadata
    ) -> DataObject:
        """
        Store processed data and create a data object record.
        
        Args:
            execution_id: ID of the execution that produced the data
            data: The actual data to store
            content_type: MIME type of the data
            metadata: Additional metadata about the data
            
        Returns:
            DataObject: Created data object record
            
        Raises:
            StorageException: If storage operation fails
            ValidationException: If metadata is invalid
        """
        ...

    async def get_data(self, object_id: DataObjectID) -> AsyncContextManager[bytes]:
        """
        Retrieve stored data as an async context manager.
        
        Args:
            object_id: ID of the data object to retrieve
            
        Returns:
            AsyncContextManager[bytes]: Context manager for accessing the data
            
        Raises:
            StorageException: If data cannot be retrieved
        """
        ...

    async def list_objects(
        self,
        execution_id: Optional[ExecutionID] = None,
        content_type: Optional[str] = None
    ) -> List[DataObject]:
        """
        List stored data objects with optional filtering.
        
        Args:
            execution_id: Optional filter by execution ID
            content_type: Optional filter by content type
            
        Returns:
            List[DataObject]: List of data objects matching the filter criteria
        """
        ...


__all__ = [
    'TaskProcessor',
    'TaskScheduler',
    'TaskExecutor',
    'StorageManager'
]