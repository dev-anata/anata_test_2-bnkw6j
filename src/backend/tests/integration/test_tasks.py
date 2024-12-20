"""
Integration tests for task scheduling, execution, and management functionality.

This module provides comprehensive integration tests for the data processing pipeline's
task management capabilities, including scheduling, execution, retry policies, and
performance validation.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import pytest  # version: 7.4+
from datetime import datetime, timedelta  # version: 3.11+
from typing import Dict, List, Optional  # version: 3.11+
from uuid import uuid4

from tasks.base import BaseTask, BaseTaskExecutor
from tasks.scheduler import TaskSchedulerImpl
from tests.utils.fixtures import (
    create_test_task,
    create_test_execution,
    create_test_data_object
)
from core.types import TaskType, TaskStatus, TaskConfig, TaskResult
from core.exceptions import ValidationException, TaskException

class MockTaskProcessor:
    """Enhanced mock task processor for testing with failure simulation."""

    def __init__(self, fail_count: int = 0) -> None:
        """
        Initialize mock processor with failure simulation.

        Args:
            fail_count: Number of times to simulate failure before succeeding
        """
        self.processed_tasks: List[Dict] = []
        self.fail_count = fail_count
        self.execution_times: List[datetime] = []

    async def process(self, task: Dict) -> TaskResult:
        """
        Mock task processing with failure simulation and timing tracking.

        Args:
            task: Task to process

        Returns:
            TaskResult: Mock processing result

        Raises:
            TaskException: If simulated failure occurs
        """
        self.processed_tasks.append(task)
        self.execution_times.append(datetime.utcnow())

        if self.fail_count > 0:
            self.fail_count -= 1
            raise TaskException(
                "Simulated task failure",
                str(task['id']),
                {"attempt": len(self.processed_tasks)}
            )

        return {
            "status": "completed",
            "data": {"test_output": "success"},
            "error": None
        }

@pytest.mark.asyncio
async def test_task_scheduling(scheduler: TaskSchedulerImpl):
    """
    Test task scheduling workflow including validation and configuration.
    
    Verifies:
    - Task creation with valid configuration
    - Scheduling validation
    - Task status transitions
    - Configuration persistence
    """
    # Create test task configuration
    task_config: TaskConfig = {
        "source": "test-source",
        "parameters": {
            "test_mode": True,
            "timeout": 30
        }
    }

    # Schedule task
    task = await scheduler.schedule_task(
        task_type="scrape",
        config=task_config,
        scheduled_at=datetime.utcnow() + timedelta(minutes=5)
    )

    # Verify task creation
    assert task.id is not None
    assert task.type == "scrape"
    assert task.status == "pending"
    assert task.configuration == task_config
    assert task.scheduled_at is not None

    # Verify task appears in scheduled queue
    scheduled_tasks = await scheduler.get_scheduled_tasks(task_type="scrape")
    assert any(t.id == task.id for t in scheduled_tasks)

    # Test invalid configuration
    with pytest.raises(ValidationException):
        await scheduler.schedule_task(
            task_type="scrape",
            config={"invalid": "config"}
        )

@pytest.mark.asyncio
async def test_task_execution(executor: BaseTaskExecutor):
    """
    Test task execution workflow and performance requirements.
    
    Verifies:
    - Task execution success
    - Performance SLA (<5min)
    - Result validation
    - Status transitions
    """
    # Create test task
    task = await create_test_task(
        task_type="scrape",
        config={"source": "test-source", "parameters": {"test_mode": True}}
    )

    # Execute task and measure time
    start_time = datetime.utcnow()
    execution = await executor.execute(task)
    end_time = datetime.utcnow()

    # Verify execution record
    assert execution.id is not None
    assert execution.task_id == task.id
    assert execution.status == "completed"
    assert execution.result is not None
    assert execution.start_time >= start_time
    assert execution.end_time <= end_time

    # Verify performance SLA
    execution_time = (end_time - start_time).total_seconds()
    assert execution_time < 300  # 5 minute SLA

    # Verify task status update
    assert task.status == "completed"
    assert len(task.execution_history) == 1
    assert task.execution_history[0] == execution.id

@pytest.mark.asyncio
async def test_task_retry_policy(executor: BaseTaskExecutor):
    """
    Test task retry behavior and backoff policy.
    
    Verifies:
    - Retry attempts
    - Backoff intervals
    - Final success
    - Error handling
    """
    # Create test task with retry policy
    task = await create_test_task(
        task_type="scrape",
        config={
            "source": "test-source",
            "parameters": {
                "test_mode": True,
                "retries": 3,
                "backoff_factor": 2
            }
        }
    )

    # Configure mock processor to fail twice
    processor = MockTaskProcessor(fail_count=2)
    executor._task_handler.register_processor(processor)

    # Execute task
    execution = await executor.execute(task)

    # Verify retry behavior
    assert len(processor.processed_tasks) == 3  # Initial + 2 retries
    assert execution.status == "completed"
    
    # Verify backoff intervals
    intervals = []
    for i in range(1, len(processor.execution_times)):
        interval = (processor.execution_times[i] - processor.execution_times[i-1]).total_seconds()
        intervals.append(interval)
    
    # Verify exponential backoff
    assert intervals[1] >= intervals[0] * 2

@pytest.mark.asyncio
async def test_task_concurrent_execution(executor: BaseTaskExecutor):
    """
    Test concurrent task execution behavior.
    
    Verifies:
    - Parallel execution
    - Resource management
    - Completion order
    - Performance under load
    """
    # Create multiple test tasks
    tasks = []
    for _ in range(5):
        task = await create_test_task(
            task_type="scrape",
            config={"source": "test-source", "parameters": {"test_mode": True}}
        )
        tasks.append(task)

    # Execute tasks concurrently
    start_time = datetime.utcnow()
    executions = await asyncio.gather(*[executor.execute(task) for task in tasks])
    end_time = datetime.utcnow()

    # Verify all executions completed
    assert len(executions) == 5
    assert all(e.status == "completed" for e in executions)

    # Verify total execution time within SLA
    total_time = (end_time - start_time).total_seconds()
    assert total_time < 300  # 5 minute SLA

    # Verify unique execution IDs
    execution_ids = [e.id for e in executions]
    assert len(set(execution_ids)) == len(execution_ids)

    # Verify task status updates
    assert all(task.status == "completed" for task in tasks)
    assert all(len(task.execution_history) == 1 for task in tasks)