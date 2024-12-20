"""
Task service implementation providing high-level business logic for task management.

This service handles task lifecycle management including creation, execution, and monitoring
with support for async operations, comprehensive error handling, and performance tracking.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
from datetime import datetime  # version: 3.11+
from typing import Dict, List, Optional, Union, AsyncIterator  # version: 3.11+
import structlog  # version: 23.1+
from aiocache import Cache  # version: 0.12+

from core.interfaces import TaskScheduler, TaskProcessor, TaskExecutor
from core.types import TaskType, TaskStatus, TaskConfig, TaskResult, TaskID
from core.exceptions import (
    ValidationException,
    TaskException,
    StorageException,
    ConfigurationException
)
from db.repositories.tasks import TaskRepository

# Configure structured logger
logger = structlog.get_logger(__name__)

# Service configuration constants
TASK_TIMEOUT_SECONDS = 300  # 5 minute timeout
MAX_RETRY_ATTEMPTS = 3
BATCH_SIZE = 100

class TaskService:
    """
    Asynchronous service layer for managing task lifecycle and operations.
    
    Features:
    - Async task creation and execution
    - Status caching and monitoring
    - Comprehensive error handling
    - Batch processing support
    - Performance tracking
    """

    def __init__(
        self,
        repository: TaskRepository,
        scheduler: TaskScheduler,
        executor: TaskExecutor
    ) -> None:
        """
        Initialize task service with required dependencies.
        
        Args:
            repository: Task data persistence layer
            scheduler: Task scheduling component
            executor: Task execution component
        """
        self._repository = repository
        self._scheduler = scheduler
        self._executor = executor
        self._processors: Dict[TaskType, TaskProcessor] = {}
        
        # Initialize status cache with 5 minute TTL
        self._status_cache = Cache(
            cache_class="aiocache.SimpleMemoryCache",
            ttl=300,
            namespace="task_status"
        )
        
        logger.info("Initialized task service")

    async def register_processor(self, processor: TaskProcessor) -> None:
        """
        Register a task processor for a specific task type.
        
        Args:
            processor: Task processor implementation
            
        Raises:
            ConfigurationException: If processor type already registered
        """
        if processor.processor_type in self._processors:
            raise ConfigurationException(
                "Processor already registered",
                {"task_type": processor.processor_type}
            )
            
        self._processors[processor.processor_type] = processor
        logger.info(
            "Registered task processor",
            task_type=processor.processor_type
        )

    async def create_task(
        self,
        task_type: TaskType,
        config: TaskConfig,
        scheduled_at: Optional[datetime] = None
    ) -> TaskID:
        """
        Create and schedule a new task.
        
        Args:
            task_type: Type of task to create
            config: Task configuration
            scheduled_at: Optional scheduled execution time
            
        Returns:
            UUID of created task
            
        Raises:
            ValidationException: If task configuration is invalid
            ConfigurationException: If no processor registered for task type
        """
        try:
            # Validate task type has registered processor
            if task_type not in self._processors:
                raise ConfigurationException(
                    "No processor registered for task type",
                    {"task_type": task_type}
                )

            # Create and schedule task
            task = await self._scheduler.schedule_task(
                task_type=task_type,
                config=config,
                scheduled_at=scheduled_at
            )
            
            # Persist task
            created_task = await self._repository.create(task)
            
            # Cache initial status
            await self._status_cache.set(
                str(created_task.id),
                created_task.status
            )
            
            logger.info(
                "Created task",
                task_id=str(created_task.id),
                task_type=task_type
            )
            
            return created_task.id

        except (ValidationException, ConfigurationException) as e:
            logger.error(
                "Failed to create task",
                task_type=task_type,
                error=str(e)
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error creating task",
                task_type=task_type,
                error=str(e)
            )
            raise TaskException(
                "Task creation failed",
                str(task_type),
                {"error": str(e)}
            )

    async def execute_task(self, task_id: TaskID) -> TaskResult:
        """
        Execute a task with timeout and error handling.
        
        Args:
            task_id: ID of task to execute
            
        Returns:
            Result of task execution
            
        Raises:
            TaskException: If execution fails
            ValidationException: If task not found or invalid state
        """
        try:
            # Get task
            task = await self._repository.get(task_id)
            if not task:
                raise ValidationException(
                    "Task not found",
                    {"task_id": str(task_id)}
                )

            # Validate task can be executed
            if task.status not in ["pending", "failed"]:
                raise ValidationException(
                    "Task cannot be executed in current state",
                    {"task_id": str(task_id), "status": task.status}
                )

            # Get processor
            processor = self._processors.get(task.type)
            if not processor:
                raise ConfigurationException(
                    "No processor registered for task type",
                    {"task_type": task.type}
                )

            # Start execution timer
            start_time = datetime.utcnow()
            
            # Execute with timeout
            try:
                execution = await asyncio.wait_for(
                    self._executor.execute(task),
                    timeout=TASK_TIMEOUT_SECONDS
                )
                
                result = await processor.process(task)
                
                # Update task status
                task.status = "completed"
                await self._repository.update(task)
                
                # Update cache
                await self._status_cache.set(str(task_id), "completed")
                
                logger.info(
                    "Task executed successfully",
                    task_id=str(task_id),
                    duration=(datetime.utcnow() - start_time).total_seconds()
                )
                
                return result

            except asyncio.TimeoutError:
                logger.error(
                    "Task execution timed out",
                    task_id=str(task_id),
                    timeout=TASK_TIMEOUT_SECONDS
                )
                task.status = "failed"
                await self._repository.update(task)
                await self._status_cache.set(str(task_id), "failed")
                raise TaskException(
                    "Task execution timed out",
                    str(task_id),
                    {"timeout": TASK_TIMEOUT_SECONDS}
                )

        except (ValidationException, ConfigurationException) as e:
            logger.error(
                "Failed to execute task",
                task_id=str(task_id),
                error=str(e)
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error executing task",
                task_id=str(task_id),
                error=str(e)
            )
            raise TaskException(
                "Task execution failed",
                str(task_id),
                {"error": str(e)}
            )

    async def batch_process(self, task_ids: List[TaskID]) -> AsyncIterator[TaskResult]:
        """
        Process multiple tasks in batches with concurrent execution.
        
        Args:
            task_ids: List of task IDs to process
            
        Returns:
            AsyncIterator yielding task results as they complete
            
        Raises:
            TaskException: If batch processing fails
        """
        try:
            # Validate task IDs
            if not task_ids:
                raise ValidationException("No task IDs provided")
            
            # Process in batches
            for i in range(0, len(task_ids), BATCH_SIZE):
                batch = task_ids[i:i + BATCH_SIZE]
                
                # Execute batch concurrently
                tasks = [
                    self.execute_task(task_id)
                    for task_id in batch
                ]
                
                # Stream results as they complete
                for result in asyncio.as_completed(tasks):
                    try:
                        yield await result
                    except Exception as e:
                        logger.error(
                            "Task in batch failed",
                            error=str(e)
                        )
                        # Continue processing remaining tasks
                        continue

            logger.info(
                "Completed batch processing",
                total_tasks=len(task_ids)
            )

        except Exception as e:
            logger.error(
                "Batch processing failed",
                error=str(e)
            )
            raise TaskException(
                "Batch processing failed",
                str(task_ids[0]),
                {"error": str(e)}
            )

    async def get_task_status(self, task_id: TaskID) -> TaskStatus:
        """
        Get current task status with caching.
        
        Args:
            task_id: ID of task to check
            
        Returns:
            Current task status
            
        Raises:
            ValidationException: If task not found
        """
        try:
            # Check cache first
            cached_status = await self._status_cache.get(str(task_id))
            if cached_status:
                return cached_status

            # Get from repository
            task = await self._repository.get(task_id)
            if not task:
                raise ValidationException(
                    "Task not found",
                    {"task_id": str(task_id)}
                )

            # Update cache
            await self._status_cache.set(str(task_id), task.status)
            
            return task.status

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                "Failed to get task status",
                task_id=str(task_id),
                error=str(e)
            )
            raise TaskException(
                "Status check failed",
                str(task_id),
                {"error": str(e)}
            )