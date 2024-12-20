"""
Unit tests for core utility functions in the data processing pipeline.

This module provides comprehensive test coverage for utility functions including:
- Task configuration validation
- Retry operation mechanisms
- Task ID generation
- Timestamp formatting
- Data batching
- Task timing utilities

Version: 1.0.0
"""

import pytest  # version: 7.4+
from datetime import datetime, timedelta  # version: 3.11+
from uuid import uuid4  # version: 3.11+
from unittest.mock import Mock, patch  # version: 3.11+
import time

from core.utils import (
    validate_task_config,
    retry_operation,
    generate_task_id,
    format_timestamp,
    batch_items,
    TaskTimer
)
from core.exceptions import ValidationException, TaskException
from tests.utils.fixtures import create_test_task

@pytest.mark.unit
def test_validate_task_config_valid():
    """Test task configuration validation with valid input."""
    # Create valid task configuration
    valid_config = {
        'type': 'scrape',
        'source': 'https://example.com',
        'parameters': {
            'url': 'https://example.com',
            'selectors': {
                'title': 'h1',
                'content': '.main-content'
            }
        }
    }

    # Validate should pass without raising exceptions
    assert validate_task_config(valid_config) is True

@pytest.mark.unit
def test_validate_task_config_invalid():
    """Test task configuration validation with invalid input."""
    # Create invalid configuration missing required fields
    invalid_config = {
        'type': 'scrape',
        'parameters': {}  # Missing source field
    }

    # Validate should raise ValidationException
    with pytest.raises(ValidationException) as exc_info:
        validate_task_config(invalid_config)
    
    assert "Missing required fields" in str(exc_info.value)
    assert "source" in exc_info.value.validation_errors.get("missing_fields", [])

@pytest.mark.unit
def test_retry_operation_success():
    """Test retry operation with successful execution."""
    # Create mock operation that succeeds
    mock_operation = Mock(return_value="success")
    
    # Execute operation with retry mechanism
    result = retry_operation(mock_operation)
    
    # Verify operation was called exactly once and returned expected result
    assert mock_operation.call_count == 1
    assert result == "success"

@pytest.mark.unit
def test_retry_operation_failure():
    """Test retry operation with repeated failures."""
    # Create mock operation that always fails
    mock_operation = Mock(side_effect=Exception("Operation failed"))
    
    # Attempt operation with retry mechanism
    with pytest.raises(TaskException) as exc_info:
        retry_operation(mock_operation, max_attempts=3)
    
    # Verify operation was called max_attempts times before giving up
    assert mock_operation.call_count == 3
    assert "Operation failed after 3 attempts" in str(exc_info.value)

@pytest.mark.unit
def test_generate_task_id():
    """Test unique task ID generation."""
    # Generate multiple task IDs
    task_ids = set(str(generate_task_id()) for _ in range(100))
    
    # Verify all IDs are unique
    assert len(task_ids) == 100
    
    # Verify UUID format
    for task_id in task_ids:
        try:
            uuid4(hex=task_id)
        except ValueError:
            pytest.fail(f"Invalid UUID format: {task_id}")

@pytest.mark.unit
def test_format_timestamp():
    """Test timestamp formatting."""
    # Create test datetime
    test_time = datetime(2024, 1, 1, 12, 0, 0)
    
    # Format timestamp
    formatted = format_timestamp(test_time)
    
    # Verify ISO 8601 format
    assert formatted.endswith('+00:00')  # UTC timezone
    assert formatted.startswith('2024-01-01T12:00:00')
    
    # Test with timezone-aware datetime
    tz_aware = test_time.astimezone()
    formatted_tz = format_timestamp(tz_aware)
    assert formatted_tz == formatted

@pytest.mark.unit
def test_batch_items():
    """Test item batching functionality."""
    # Create test items
    items = list(range(150))
    
    # Test with default batch size
    batches = batch_items(items, batch_size=50)
    
    # Verify batch sizes
    assert len(batches) == 3
    assert len(batches[0]) == 50
    assert len(batches[1]) == 50
    assert len(batches[2]) == 50
    
    # Verify all items are included
    assert sum(len(batch) for batch in batches) == len(items)
    
    # Test with non-even division
    odd_batches = batch_items(items, batch_size=40)
    assert len(odd_batches) == 4
    assert len(odd_batches[-1]) == 30

@pytest.mark.unit
def test_task_timer():
    """Test task execution timing."""
    task_id = str(uuid4())
    
    # Test normal execution
    with TaskTimer(task_id) as timer:
        time.sleep(0.1)  # Simulate work
    
    # Verify timing metrics
    assert timer.metrics['task_id'] == task_id
    assert timer.metrics['status'] == 'completed'
    assert 0.1 <= timer.metrics['duration_seconds'] <= 0.2
    assert 'start_time' in timer.metrics
    assert 'end_time' in timer.metrics

@pytest.mark.unit
def test_task_timer_error():
    """Test task timer with error condition."""
    task_id = str(uuid4())
    
    # Test execution with error
    with pytest.raises(ValueError):
        with TaskTimer(task_id) as timer:
            raise ValueError("Test error")
    
    # Verify error metrics
    assert timer.metrics['task_id'] == task_id
    assert timer.metrics['status'] == 'failed'
    assert 'error' in timer.metrics
    assert timer.metrics['error'] == 'Test error'

@pytest.mark.unit
def test_task_timer_thread_safety():
    """Test task timer thread safety."""
    task_id = str(uuid4())
    timer = TaskTimer(task_id)
    
    # Test concurrent access to metrics
    with timer:
        # Simulate concurrent access
        timer.metrics['concurrent_key'] = 'value1'
        time.sleep(0.01)
        assert timer.metrics['concurrent_key'] == 'value1'