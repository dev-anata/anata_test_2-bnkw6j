"""
Enhanced task scheduler implementation for managing and scheduling data processing tasks.

This module provides a robust implementation of the TaskScheduler protocol with 
comprehensive error handling, performance monitoring, and task validation capabilities.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
from datetime import datetime, timedelta  # version: 3.11+
from typing import Dict, Optional, List, TypedDict  # version: 3.11+
import logging
from uuid import uuid4

from google.cloud import pubsub_v1  # version: 2.18+
from google.api_core import retry  # version: 2.18+

from core.interfaces import TaskScheduler
from core.models import Task, TaskMetrics
from core.types import TaskType, TaskStatus, TaskConfig, TaskID, RetryPolicy
from core.exceptions import ValidationException, TaskException, ConfigurationException
from tasks.base import BaseTask

# Configure logging
logger = logging.getLogger(__name__)

class TaskSchedulerImpl(TaskScheduler):
    """
    Enhanced implementation of TaskScheduler with comprehensive error handling,
    performance monitoring, and task validation capabilities.
    """

    def __init__(self, project_id: str, topic_id: str, dlq_topic_id: str) -> None:
        """
        Initialize task scheduler with Pub/Sub publisher and monitoring.

        Args:
            project_id: GCP project ID
            topic_id: Main Pub/Sub topic ID
            dlq_topic_id: Dead letter queue topic ID

        Raises:
            ConfigurationException: If initialization fails
        """
        try:
            # Initialize Pub/Sub publisher with retry settings
            publisher_options = pubsub_v1.types.PublisherOptions(
                enable_message_ordering=True
            )
            retry_settings = retry.RetrySettings(
                initial_retry_delay=1.0,  # seconds
                retry_delay_multiplier=1.3,
                max_retry_delay=60.0,  # seconds
                initial_rpc_timeout=60.0,  # seconds
                rpc_timeout_multiplier=1.0,
                max_rpc_timeout=600.0,  # seconds
                total_timeout=600.0  # seconds
            )
            self._publisher = pubsub_v1.PublisherClient(
                publisher_options=publisher_options
            )
            
            # Set up topics
            self._topic_path = self._publisher.topic_path(project_id, topic_id)
            self._dlq_topic_path = self._publisher.topic_path(project_id, dlq_topic_id)
            
            # Initialize task handlers and metrics storage
            self._task_handlers: Dict[TaskType, BaseTask] = {}
            self._task_metrics: Dict[TaskID, TaskMetrics] = {}
            
            logger.info("Task scheduler initialized successfully")
            
        except Exception as e:
            raise ConfigurationException(
                "Failed to initialize task scheduler",
                {"error": str(e), "project_id": project_id}
            )

    async def schedule_task(
        self,
        task_type: TaskType,
        config: TaskConfig,
        scheduled_at: Optional[datetime] = None,
        retry_policy: Optional[RetryPolicy] = None
    ) -> Task:
        """
        Schedule a new task with enhanced validation and monitoring.

        Args:
            task_type: Type of task to schedule
            config: Task configuration
            scheduled_at: Optional scheduled execution time
            retry_policy: Optional retry configuration

        Returns:
            Task: Created and scheduled task

        Raises:
            ValidationException: If task configuration is invalid
            TaskException: If scheduling fails
        """
        try:
            # Validate task type and handler
            if task_type not in self._task_handlers:
                raise ValidationException(
                    "Invalid task type",
                    {"available_types": list(self._task_handlers.keys())}
                )
            
            handler = self._task_handlers[task_type]
            
            # Validate task configuration
            await handler.validate_config(config)
            
            # Create new task
            task = Task(
                id=uuid4(),
                type=task_type,
                status="pending",
                configuration=config,
                scheduled_at=scheduled_at
            )
            
            # Initialize task metrics
            self._task_metrics[task.id] = TaskMetrics(
                task_id=task.id,
                created_at=datetime.utcnow(),
                retry_count=0,
                last_retry=None,
                execution_time=None,
                error_count=0
            )
            
            # Prepare message attributes
            message_attributes = {
                "task_id": str(task.id),
                "task_type": task_type,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else "",
            }
            
            if retry_policy:
                message_attributes.update({
                    "max_retries": str(retry_policy.get("max_retries", 3)),
                    "retry_delay": str(retry_policy.get("retry_delay_seconds", 60))
                })
            
            # Publish task to Pub/Sub
            message_data = str(task.id).encode("utf-8")
            future = self._publisher.publish(
                self._topic_path,
                message_data,
                **message_attributes
            )
            
            # Wait for publish confirmation
            try:
                message_id = future.result(timeout=60)
                logger.info(f"Task {task.id} scheduled successfully: {message_id}")
            except Exception as e:
                raise TaskException(
                    "Failed to publish task",
                    str(task.id),
                    {"error": str(e)}
                )
            
            return task
            
        except ValidationException:
            raise
        except Exception as e:
            raise TaskException(
                "Failed to schedule task",
                str(task.id) if 'task' in locals() else "unknown",
                {"error": str(e)}
            )

    async def cancel_task(self, task_id: TaskID) -> bool:
        """
        Cancel a scheduled or running task with cleanup.

        Args:
            task_id: ID of task to cancel

        Returns:
            bool: True if task was cancelled successfully

        Raises:
            TaskException: If cancellation fails
        """
        try:
            # Publish cancellation message
            message_data = str(task_id).encode("utf-8")
            future = self._publisher.publish(
                self._topic_path,
                message_data,
                operation="cancel",
                task_id=str(task_id)
            )
            
            # Wait for confirmation
            try:
                message_id = future.result(timeout=60)
                logger.info(f"Task {task_id} cancellation published: {message_id}")
            except Exception as e:
                raise TaskException(
                    "Failed to publish cancellation",
                    str(task_id),
                    {"error": str(e)}
                )
            
            # Clean up metrics
            if task_id in self._task_metrics:
                metrics = self._task_metrics[task_id]
                metrics.cancelled_at = datetime.utcnow()
                
            return True
            
        except Exception as e:
            raise TaskException(
                "Failed to cancel task",
                str(task_id),
                {"error": str(e)}
            )

    async def handle_task_failure(self, task_id: TaskID, error: Exception) -> None:
        """
        Handle task failure with retry logic and dead letter queue.

        Args:
            task_id: ID of failed task
            error: Exception that caused the failure
        """
        try:
            # Update metrics
            if task_id in self._task_metrics:
                metrics = self._task_metrics[task_id]
                metrics.error_count += 1
                metrics.last_error = str(error)
                metrics.last_error_at = datetime.utcnow()
                
                # Check retry policy
                if metrics.retry_count < metrics.max_retries:
                    # Schedule retry
                    retry_delay = metrics.base_retry_delay * (2 ** metrics.retry_count)
                    scheduled_at = datetime.utcnow() + timedelta(seconds=retry_delay)
                    
                    message_data = str(task_id).encode("utf-8")
                    future = self._publisher.publish(
                        self._topic_path,
                        message_data,
                        operation="retry",
                        task_id=str(task_id),
                        retry_count=str(metrics.retry_count + 1),
                        scheduled_at=scheduled_at.isoformat()
                    )
                    
                    await future.result(timeout=60)
                    metrics.retry_count += 1
                    metrics.last_retry = datetime.utcnow()
                    
                else:
                    # Move to DLQ
                    future = self._publisher.publish(
                        self._dlq_topic_path,
                        message_data,
                        task_id=str(task_id),
                        error=str(error),
                        retry_count=str(metrics.retry_count)
                    )
                    await future.result(timeout=60)
                    logger.error(f"Task {task_id} moved to DLQ after {metrics.retry_count} retries")
            
        except Exception as e:
            logger.error(f"Error handling task failure: {str(e)}")

    async def monitor_task_performance(self, task_id: TaskID) -> TaskMetrics:
        """
        Monitor task execution performance and SLA compliance.

        Args:
            task_id: ID of task to monitor

        Returns:
            TaskMetrics: Current task performance metrics

        Raises:
            TaskException: If monitoring fails
        """
        try:
            if task_id not in self._task_metrics:
                raise TaskException(
                    "Task metrics not found",
                    str(task_id)
                )
                
            metrics = self._task_metrics[task_id]
            
            # Check SLA compliance
            if metrics.execution_time:
                execution_minutes = metrics.execution_time.total_seconds() / 60
                if execution_minutes > 5:  # 5-minute SLA
                    logger.warning(f"Task {task_id} exceeded SLA: {execution_minutes} minutes")
                    
            return metrics
            
        except Exception as e:
            raise TaskException(
                "Failed to monitor task performance",
                str(task_id),
                {"error": str(e)}
            )