"""
Base task implementation providing core functionality for task processing, scheduling,
and execution in the data processing pipeline with enhanced error handling and monitoring.

This module implements the foundational task management capabilities including processor
registration, task validation, execution handling, and comprehensive error management.

Version: 1.0.0
"""

from abc import ABC, abstractmethod  # version: 3.11+
import asyncio  # version: 3.11+
from datetime import datetime, timedelta  # version: 3.11+
from typing import Dict, Optional, List  # version: 3.11+
import logging

from core.interfaces import TaskProcessor, TaskScheduler, TaskExecutor
from core.types import TaskType, TaskStatus, TaskConfig, TaskResult, TaskID, ExecutionID
from core.models import Task, TaskExecution
from core.exceptions import (
    ValidationException, TaskException, ConfigurationException, PipelineException
)

# Configure logging
logger = logging.getLogger(__name__)

class BaseTask(ABC):
    """
    Abstract base class implementing common task functionality with enhanced error handling
    and monitoring capabilities.
    """

    def __init__(self) -> None:
        """Initialize base task with processor registry and monitoring."""
        self._processors: Dict[str, TaskProcessor] = {}
        self._retry_counts: Dict[str, int] = {}
        self._last_failures: Dict[str, datetime] = {}
        self._success_rates: Dict[str, float] = {}
        self._circuit_breakers: Dict[str, bool] = {}
        self._max_retries = 3
        self._cooldown_period = timedelta(minutes=5)
        self._failure_threshold = 0.3

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        """Get the type of task this class handles."""
        pass

    def register_processor(self, processor: TaskProcessor) -> None:
        """
        Register a task processor for a specific task type with validation.

        Args:
            processor: The processor instance to register

        Raises:
            ValidationException: If processor is invalid or incompatible
            ConfigurationException: If processor registration fails
        """
        try:
            # Validate processor implements required interface
            if not isinstance(processor, TaskProcessor):
                raise ValidationException(
                    "Invalid processor type",
                    {"expected": "TaskProcessor", "received": type(processor).__name__}
                )

            # Initialize monitoring metrics for the processor
            processor_id = str(id(processor))
            self._retry_counts[processor_id] = 0
            self._success_rates[processor_id] = 1.0
            self._circuit_breakers[processor_id] = False
            self._processors[processor_id] = processor

            logger.info(f"Registered processor {processor_id} for task type {self.task_type}")

        except Exception as e:
            raise ConfigurationException(
                "Failed to register processor",
                {"error": str(e), "processor_type": processor.processor_type}
            )

    async def get_processor(self, task_type: TaskType) -> TaskProcessor:
        """
        Get appropriate processor for task type with circuit breaker pattern.

        Args:
            task_type: Type of task to process

        Returns:
            TaskProcessor: The appropriate processor instance

        Raises:
            TaskException: If no suitable processor is available
            ConfigurationException: If processor is in circuit breaker state
        """
        try:
            # Find available processor
            for processor_id, processor in self._processors.items():
                # Check circuit breaker status
                if self._circuit_breakers[processor_id]:
                    logger.warning(f"Processor {processor_id} circuit breaker is open")
                    continue

                # Check processor health
                if self._success_rates[processor_id] < self._failure_threshold:
                    self._circuit_breakers[processor_id] = True
                    logger.error(f"Circuit breaker triggered for processor {processor_id}")
                    continue

                # Check cooldown period
                last_failure = self._last_failures.get(processor_id)
                if last_failure and datetime.utcnow() - last_failure < self._cooldown_period:
                    continue

                if processor.processor_type == task_type:
                    return processor

            raise TaskException(
                "No available processor found",
                str(task_type),
                {"available_processors": list(self._processors.keys())}
            )

        except Exception as e:
            raise ConfigurationException(
                "Failed to get processor",
                {"task_type": task_type, "error": str(e)}
            )

    @abstractmethod
    async def validate_config(self, config: TaskConfig) -> bool:
        """
        Validate task configuration with enhanced checks.

        Args:
            config: Task configuration to validate

        Returns:
            bool: True if configuration is valid

        Raises:
            ValidationException: If configuration is invalid
        """
        pass


class BaseTaskExecutor:
    """Base implementation of task executor with comprehensive error handling."""

    def __init__(self, task_handler: BaseTask) -> None:
        """
        Initialize executor with task handler and monitoring.

        Args:
            task_handler: Base task handler instance
        """
        self._task_handler = task_handler
        self._retry_policies: Dict[str, int] = {}
        self._cooldown_periods: Dict[str, datetime] = {}
        self._resource_limits: Dict[str, float] = {}
        self._execution_timeout = 300  # 5 minutes default timeout

    async def execute(self, task: Task) -> TaskExecution:
        """
        Execute a task using appropriate processor with full error handling.

        Args:
            task: Task to execute

        Returns:
            TaskExecution: Record of the task execution

        Raises:
            TaskException: If execution fails
            ValidationException: If task is invalid
        """
        # Create execution record
        execution = TaskExecution(task_id=task.id)
        task.add_execution(execution.id)

        try:
            # Validate task state
            if task.status != "pending":
                raise ValidationException(
                    "Invalid task status for execution",
                    {"current_status": task.status, "required_status": "pending"}
                )

            # Get appropriate processor
            processor = await self._task_handler.get_processor(task.type)

            # Update task status
            task.update_status("running")

            # Execute with timeout
            try:
                async with asyncio.timeout(self._execution_timeout):
                    result = await processor.process(task)
            except asyncio.TimeoutError:
                raise TaskException(
                    "Task execution timed out",
                    str(task.id),
                    {"timeout_seconds": self._execution_timeout}
                )

            # Handle successful execution
            execution.complete(result)
            task.update_status("completed")
            return execution

        except Exception as e:
            # Handle execution failure
            await self.handle_failure(execution, e)
            task.update_status("failed")
            raise

    async def handle_failure(self, execution: TaskExecution, error: Exception) -> None:
        """
        Handle task execution failures with retry logic.

        Args:
            execution: Failed execution record
            error: Exception that caused the failure
        """
        error_message = str(error)
        error_context = {
            "execution_id": str(execution.id),
            "task_id": str(execution.task_id),
            "error_type": type(error).__name__
        }

        # Log error details
        logger.error(f"Task execution failed: {error_message}", extra=error_context)

        # Update execution record
        execution.fail(error_message)

        # Update monitoring metrics
        processor_id = str(id(self._task_handler))
        self._task_handler._retry_counts[processor_id] += 1
        self._task_handler._last_failures[processor_id] = datetime.utcnow()

        # Calculate new success rate
        total_attempts = self._task_handler._retry_counts[processor_id]
        success_rate = 1 - (total_attempts / (total_attempts + 1))
        self._task_handler._success_rates[processor_id] = success_rate


__all__ = ['BaseTask', 'BaseTaskExecutor']