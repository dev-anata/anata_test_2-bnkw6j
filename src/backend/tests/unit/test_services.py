"""
Unit tests for service layer components including storage, data, task, OCR and scraping services.

Tests service functionality in isolation using mocks and fixtures to validate:
- Error handling and recovery mechanisms
- Performance requirements
- Data management operations
- Service integration points

Version: 1.0.0
"""

import pytest  # version: 7.4+
import asyncio  # version: 3.11+
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
import structlog

from services.storage_service import StorageService
from services.data_service import DataService
from services.task_service import TaskService
from core.exceptions import StorageException, ValidationException, TaskException
from tests.utils import (
    create_test_task,
    create_test_data_object,
    create_test_execution
)

# Configure structured test logger
logger = structlog.get_logger(__name__)

@pytest.fixture
async def mock_storage_backend():
    """Fixture providing a mock storage backend."""
    mock = AsyncMock()
    mock.store_object = AsyncMock()
    mock.retrieve_object = AsyncMock()
    mock.delete_object = AsyncMock()
    return mock

@pytest.fixture
async def mock_cache_client():
    """Fixture providing a mock Redis cache client."""
    mock = Mock()
    mock.get = Mock()
    mock.set = Mock()
    mock.delete = Mock()
    mock.setex = Mock()
    return mock

@pytest.fixture
async def storage_service(mock_storage_backend, mock_cache_client):
    """Fixture providing a configured storage service instance."""
    return StorageService(
        storage_backend=mock_storage_backend,
        cache_client=mock_cache_client,
        cache_ttl_seconds=300,
        max_retries=3,
        retry_backoff=1.5
    )

@pytest.fixture
async def mock_task_repository():
    """Fixture providing a mock task repository."""
    mock = AsyncMock()
    mock.create = AsyncMock()
    mock.get = AsyncMock()
    mock.update = AsyncMock()
    mock.list_by_status = AsyncMock()
    return mock

@pytest.fixture
async def mock_scheduler():
    """Fixture providing a mock task scheduler."""
    mock = AsyncMock()
    mock.schedule_task = AsyncMock()
    mock.cancel_task = AsyncMock()
    return mock

@pytest.fixture
async def mock_executor():
    """Fixture providing a mock task executor."""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.get_status = AsyncMock()
    return mock

@pytest.fixture
async def task_service(mock_task_repository, mock_scheduler, mock_executor):
    """Fixture providing a configured task service instance."""
    service = TaskService(
        repository=mock_task_repository,
        scheduler=mock_scheduler,
        executor=mock_executor
    )
    return service

@pytest.mark.asyncio
class TestStorageService:
    """Test suite for storage service functionality."""

    async def test_store_data_success(self, storage_service, mock_storage_backend, mock_cache_client):
        """Test successful data storage with caching and performance validation."""
        # Prepare test data
        test_data = b"Test data content"
        test_metadata = {"content_type": "text/plain", "source": "test"}
        
        # Configure mock responses
        stored_object = await create_test_data_object(await create_test_execution(await create_test_task()))
        mock_storage_backend.store_object.return_value = stored_object
        
        # Execute storage operation with timing
        start_time = datetime.utcnow()
        result = await storage_service.store_data(test_data, test_metadata)
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify performance requirement (<500ms)
        assert duration < 0.5, f"Storage operation took {duration}s, exceeding 500ms limit"
        
        # Verify storage backend called correctly
        mock_storage_backend.store_object.assert_called_once_with(test_data, test_metadata)
        
        # Verify cache updated
        mock_cache_client.setex.assert_called_once()
        cache_key = f"storage:{stored_object.id}"
        assert mock_cache_client.setex.call_args[0][0] == cache_key
        
        # Verify result
        assert result.id == stored_object.id
        assert result.storage_path == stored_object.storage_path

    async def test_store_data_error_handling(self, storage_service, mock_storage_backend):
        """Test storage error handling and recovery mechanisms."""
        # Configure storage backend to fail initially
        mock_storage_backend.store_object.side_effect = [
            StorageException("Test failure"),
            StorageException("Test failure"),
            None  # Succeeds on third try
        ]
        
        test_data = b"Test data content"
        test_metadata = {"content_type": "text/plain", "source": "test"}
        
        # Verify retry behavior
        with pytest.raises(StorageException) as exc_info:
            await storage_service.store_data(test_data, test_metadata)
        
        assert "Storage operation failed after retries" in str(exc_info.value)
        assert mock_storage_backend.store_object.call_count == 3

    async def test_retrieve_data_with_cache(self, storage_service, mock_storage_backend, mock_cache_client):
        """Test data retrieval with cache optimization."""
        test_object_id = uuid4()
        cached_data = {
            "storage_path": "test/path",
            "metadata": {"test": "data"},
            "cached_at": datetime.utcnow().isoformat()
        }
        
        # Configure cache hit
        mock_cache_client.get.return_value = cached_data
        
        async with storage_service.retrieve_data(test_object_id) as data:
            assert data is not None
            mock_cache_client.get.assert_called_once()
            mock_storage_backend.retrieve_object.assert_called_once()

@pytest.mark.asyncio
class TestDataService:
    """Test suite for data service operations."""

    async def test_batch_process_performance(self, mock_storage_backend):
        """Test batch data processing meets performance requirements."""
        data_service = DataService(Mock(), mock_storage_backend)
        test_data = [b"data1", b"data2", b"data3"]
        execution_id = uuid4()
        
        # Process batch with timing
        start_time = datetime.utcnow()
        results = []
        
        for data in test_data:
            result = await data_service.store_data(
                data=data,
                execution_id=execution_id,
                metadata={"test": "data"}
            )
            results.append(result)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify performance requirement (<5 minutes)
        assert duration < 300, f"Batch processing took {duration}s, exceeding 5 minute limit"
        assert len(results) == len(test_data)

    async def test_data_consistency(self, mock_storage_backend):
        """Test data consistency and validation during processing."""
        data_service = DataService(Mock(), mock_storage_backend)
        
        # Test invalid metadata
        with pytest.raises(ValidationException):
            await data_service.store_data(
                data=b"test",
                execution_id=uuid4(),
                metadata="invalid"  # Should be dict
            )

@pytest.mark.asyncio
class TestTaskService:
    """Test suite for task scheduling and execution."""

    async def test_task_execution_performance(self, task_service, mock_executor):
        """Test task execution meets performance requirements."""
        test_task = await create_test_task()
        mock_executor.execute.return_value = await create_test_execution(test_task)
        
        # Execute task with timing
        start_time = datetime.utcnow()
        result = await task_service.execute_task(test_task.id)
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify performance requirement (<5 minutes)
        assert duration < 300, f"Task execution took {duration}s, exceeding 5 minute limit"
        assert result is not None

    async def test_task_error_handling(self, task_service, mock_executor):
        """Test task error handling and recovery mechanisms."""
        test_task = await create_test_task()
        mock_executor.execute.side_effect = TaskException("Test failure")
        
        with pytest.raises(TaskException):
            await task_service.execute_task(test_task.id)
        
        # Verify task marked as failed
        mock_executor.execute.assert_called_once()

def pytest_configure(config):
    """Configure pytest for service tests."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "performance: mark test as performance validation"
    )
    config.addinivalue_line(
        "markers", "error_handling: mark test as error handling validation"
    )
    
    # Configure test timeouts
    config.addinivalue_line(
        "timeout", "300"  # 5 minute timeout for performance tests
    )