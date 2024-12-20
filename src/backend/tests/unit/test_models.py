"""
Unit tests for core data models.

This module provides comprehensive test coverage for the Task, TaskExecution, and DataObject
models, validating their behavior, data validation, state transitions, and relationships.

Version: 1.0.0
"""

import pytest  # version: 7.4+
from datetime import datetime, timedelta  # version: 3.11+
from uuid import uuid4  # version: 3.11+

from core.models import Task, TaskExecution, DataObject
from core.types import TaskType, TaskStatus, TaskConfig, TaskResult
from core.exceptions import ValidationException
from tests.utils.factories import TaskFactory, TaskExecutionFactory, DataObjectFactory


def pytest_configure(config):
    """Configure pytest environment for model testing."""
    # Register custom markers
    config.addinivalue_line("markers", "models: mark test as a model test")
    config.addinivalue_line("markers", "task: mark test as a Task model test")
    config.addinivalue_line("markers", "execution: mark test as a TaskExecution model test")
    config.addinivalue_line("markers", "data: mark test as a DataObject model test")


@pytest.mark.models
@pytest.mark.task
class TestTask:
    """Test suite for Task model validation and behavior."""

    def test_task_creation(self):
        """Test task instance creation with valid data."""
        # Create task with valid configuration
        task = TaskFactory.create(
            type="scrape",
            configuration={
                "source": "https://example.com",
                "parameters": {"depth": 2, "timeout": 60}
            }
        )

        # Verify basic attributes
        assert task.id is not None
        assert isinstance(task.id, uuid4().__class__)
        assert task.type == "scrape"
        assert task.status == "pending"
        assert isinstance(task.created_at, datetime)
        assert task.updated_at is None
        assert task.scheduled_at is None
        assert isinstance(task.execution_history, list)
        assert len(task.execution_history) == 0

        # Verify configuration structure
        assert "source" in task.configuration
        assert "parameters" in task.configuration
        assert isinstance(task.configuration["parameters"], dict)

    def test_task_invalid_config(self):
        """Test task creation with invalid configuration."""
        # Test missing source
        with pytest.raises(ValidationException) as exc_info:
            TaskFactory.create(configuration={"parameters": {}})
        assert "Missing required configuration field" in str(exc_info.value)
        assert exc_info.value.validation_errors["field"] == "source"

        # Test invalid configuration type
        with pytest.raises(ValidationException) as exc_info:
            TaskFactory.create(configuration="invalid")
        assert "Invalid task configuration format" in str(exc_info.value)
        assert exc_info.value.validation_errors["expected"] == "dict"

    def test_task_status_transitions(self):
        """Test all valid task status transitions."""
        task = TaskFactory.create()
        assert task.status == "pending"

        # Test valid transitions
        task.update_status("running")
        assert task.status == "running"
        assert task.updated_at is not None
        previous_update = task.updated_at

        task.update_status("completed")
        assert task.status == "completed"
        assert task.updated_at > previous_update

        # Test invalid transitions
        with pytest.raises(ValidationException) as exc_info:
            task.update_status("running")
        assert "Invalid status transition" in str(exc_info.value)
        assert exc_info.value.validation_errors["current_status"] == "completed"

    def test_task_execution_tracking(self):
        """Test execution history tracking."""
        task = TaskFactory.create()
        execution_ids = [uuid4() for _ in range(3)]

        # Add executions and verify tracking
        for exec_id in execution_ids:
            task.add_execution(exec_id)
            assert exec_id in task.execution_history

        assert len(task.execution_history) == 3
        assert task.updated_at is not None

        # Verify execution order is maintained
        assert task.execution_history == execution_ids


@pytest.mark.models
@pytest.mark.execution
class TestTaskExecution:
    """Test suite for TaskExecution model."""

    def test_execution_creation(self):
        """Test execution instance creation and validation."""
        task = TaskFactory.create()
        execution = TaskExecutionFactory.create(task_id=task.id)

        # Verify basic attributes
        assert execution.id is not None
        assert isinstance(execution.id, uuid4().__class__)
        assert execution.task_id == task.id
        assert execution.status == "running"
        assert isinstance(execution.start_time, datetime)
        assert execution.end_time is None
        assert execution.result is None
        assert execution.error_message is None
        assert isinstance(execution.output_objects, list)
        assert len(execution.output_objects) == 0

    def test_execution_result_handling(self):
        """Test execution result processing and validation."""
        execution = TaskExecutionFactory.create()
        result = {
            "status": "success",
            "data": {"items_processed": 42},
            "error": None
        }

        # Complete execution with results
        execution.complete(result)
        assert execution.status == "completed"
        assert execution.result == result
        assert execution.end_time is not None
        assert execution.error_message is None

        # Verify can't complete already completed execution
        with pytest.raises(ValidationException) as exc_info:
            execution.complete(result)
        assert "Cannot complete execution with current status" in str(exc_info.value)

    def test_execution_error_handling(self):
        """Test execution error handling scenarios."""
        execution = TaskExecutionFactory.create()
        error_msg = "Test error message"

        # Fail execution with error
        execution.fail(error_msg)
        assert execution.status == "failed"
        assert execution.error_message == error_msg
        assert execution.end_time is not None
        assert execution.result is None

        # Verify can't fail already failed execution
        with pytest.raises(ValidationException) as exc_info:
            execution.fail("Another error")
        assert "Cannot fail execution with current status" in str(exc_info.value)


@pytest.mark.models
@pytest.mark.data
class TestDataObject:
    """Test suite for DataObject model."""

    def test_data_object_creation(self):
        """Test data object creation and validation."""
        execution = TaskExecutionFactory.create()
        data_object = DataObjectFactory.create(
            execution_id=execution.id,
            storage_path="test/path/data.json",
            content_type="application/json",
            metadata={
                "source": "https://example.com",
                "timestamp": datetime.utcnow().isoformat(),
                "attributes": {"type": "test"}
            }
        )

        # Verify basic attributes
        assert data_object.id is not None
        assert isinstance(data_object.id, uuid4().__class__)
        assert data_object.execution_id == execution.id
        assert data_object.storage_path == "test/path/data.json"
        assert data_object.content_type == "application/json"
        assert isinstance(data_object.created_at, datetime)

        # Test invalid storage path
        with pytest.raises(ValidationException) as exc_info:
            DataObjectFactory.create(storage_path="")
        assert "Storage path cannot be empty" in str(exc_info.value)

        # Test invalid content type
        with pytest.raises(ValidationException) as exc_info:
            DataObjectFactory.create(content_type="")
        assert "Content type cannot be empty" in str(exc_info.value)

    def test_data_object_metadata(self):
        """Test metadata handling and validation."""
        # Test valid metadata
        metadata = {
            "source": "https://example.com",
            "timestamp": datetime.utcnow().isoformat(),
            "size_bytes": 1024,
            "attributes": {
                "type": "scraped_data",
                "format": "json",
                "items": 42
            }
        }
        data_object = DataObjectFactory.create(metadata=metadata)
        assert data_object.metadata == metadata

        # Test invalid metadata type
        with pytest.raises(ValidationException) as exc_info:
            DataObjectFactory.create(metadata="invalid")
        assert "Invalid metadata format" in str(exc_info.value)
        assert exc_info.value.validation_errors["expected"] == "dict"

        # Test metadata with nested structures
        complex_metadata = {
            "source": "https://example.com",
            "timestamp": datetime.utcnow().isoformat(),
            "processing": {
                "duration_ms": 1500,
                "steps": ["fetch", "parse", "store"],
                "stats": {
                    "success": True,
                    "items": 42,
                    "errors": []
                }
            }
        }
        data_object = DataObjectFactory.create(metadata=complex_metadata)
        assert data_object.metadata == complex_metadata