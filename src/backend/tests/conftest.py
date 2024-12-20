"""
Pytest configuration file for the Data Processing Pipeline test suite.

Provides shared test fixtures and configuration for comprehensive testing of pipeline
components with support for both synchronous and asynchronous testing patterns.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from uuid import uuid4

import pytest  # version: 7.4+
import pytest_asyncio  # version: 0.21+
import structlog  # version: 23.1+

from tests.utils.fixtures import (
    create_test_task,
    create_test_execution,
    create_test_data_object
)
from tests.utils.mocks import MockTaskRepository, MockTaskService
from db.firestore import FirestoreClient
from core.exceptions import StorageException, ValidationException
from config.settings import settings

# Configure structured logging for tests
TEST_LOGGER = structlog.get_logger("test")

# Register pytest-asyncio as a plugin
pytest_plugins = ['pytest_asyncio']

# Test database configuration
TEST_DB_CONFIG = {
    'project_id': 'test-project',
    'emulator_host': 'localhost:8681',
    'timeout': 30,
    'pool_size': 10
}

@pytest.fixture(scope='session')
def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    """
    Session-scoped fixture providing event loop for async tests.
    
    Yields:
        asyncio.AbstractEventLoop: Configured event loop instance
    """
    try:
        loop = asyncio.get_event_loop_policy().new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        yield loop
    finally:
        loop.close()
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

@pytest.fixture
async def mock_task_repository() -> MockTaskRepository:
    """
    Function-scoped fixture providing mock task repository.
    
    Returns:
        MockTaskRepository: Configured mock repository instance
    """
    repository = MockTaskRepository()
    
    # Configure error triggers for testing
    repository.set_error_trigger(
        'storage_error',
        StorageException('Mock storage error', storage_path='test')
    )
    repository.set_error_trigger(
        'validation_error',
        ValidationException('Mock validation error', {'field': 'test'})
    )
    
    TEST_LOGGER.debug("Created mock task repository")
    return repository

@pytest.fixture
async def mock_task_service(mock_task_repository: MockTaskRepository) -> MockTaskService:
    """
    Function-scoped fixture providing mock task service.
    
    Args:
        mock_task_repository: Mock repository fixture
        
    Returns:
        MockTaskService: Configured mock service instance
    """
    service = MockTaskService()
    
    # Register test processors
    service.register_processor('scrape', lambda x: {'status': 'completed'})
    service.register_processor('ocr', lambda x: {'status': 'completed'})
    
    # Configure error scenarios
    service._repository = mock_task_repository
    
    TEST_LOGGER.debug("Created mock task service")
    return service

@pytest.fixture(scope='session')
@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[FirestoreClient, None]:
    """
    Session-scoped fixture providing test database client.
    
    Yields:
        FirestoreClient: Configured database client instance
    """
    try:
        # Initialize test database client
        client = FirestoreClient(
            pool_size=TEST_DB_CONFIG['pool_size'],
            timeout=TEST_DB_CONFIG['timeout']
        )
        
        # Connect to test database
        async with client.connect() as conn:
            # Verify connection
            test_doc_id = str(uuid4())
            test_data = {'test': True, 'timestamp': 'test'}
            
            try:
                await conn.collection('test').document(test_doc_id).set(test_data)
                await conn.collection('test').document(test_doc_id).delete()
                TEST_LOGGER.info("Test database connection verified")
            except Exception as e:
                TEST_LOGGER.error("Test database connection failed", error=str(e))
                raise
        
        yield client
        
        # Cleanup test data
        TEST_LOGGER.info("Cleaning up test database")
        try:
            async with client.connect() as conn:
                # Delete test collections
                collections = ['tasks', 'executions', 'data_objects', 'test']
                for collection in collections:
                    batch = conn.batch()
                    docs = await conn.collection(collection).limit(100).get()
                    for doc in docs:
                        batch.delete(doc.reference)
                    await batch.commit()
        except Exception as e:
            TEST_LOGGER.error("Test database cleanup failed", error=str(e))
            raise
        finally:
            await client.close()
            
    except Exception as e:
        TEST_LOGGER.error("Test database fixture failed", error=str(e))
        raise

@pytest.fixture(autouse=True)
def configure_test_logging():
    """
    Configure logging for test execution.
    
    This fixture runs automatically for all tests.
    """
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

@pytest.fixture(autouse=True)
def mock_gcp_credentials(monkeypatch):
    """
    Mock GCP credentials for testing.
    
    This fixture runs automatically for all tests.
    """
    mock_creds = {
        'project_id': TEST_DB_CONFIG['project_id'],
        'emulator_host': TEST_DB_CONFIG['emulator_host']
    }
    monkeypatch.setattr(settings, 'get_gcp_credentials', lambda: mock_creds)

@pytest.fixture
def test_config() -> Dict[str, Any]:
    """
    Provide test configuration values.
    
    Returns:
        Dict[str, Any]: Test configuration dictionary
    """
    return {
        'source': 'test-source',
        'parameters': {
            'test_mode': True,
            'timeout': 30,
            'retries': 1
        }
    }
```

This implementation provides a comprehensive pytest configuration with the following key features:

1. Session-scoped event loop fixture for async tests
2. Mock repository and service fixtures with error simulation
3. Test database fixture with cleanup
4. Automatic logging configuration
5. GCP credentials mocking
6. Test configuration values
7. Integration with pytest-asyncio
8. Structured logging setup
9. Database connection verification
10. Automatic cleanup of test data

The configuration follows best practices for testing including:
- Proper resource cleanup
- Isolation between tests
- Configurable error scenarios
- Comprehensive logging
- Support for both sync and async testing
- Mock implementations for external dependencies
- Database emulator support
- Automatic fixture application where appropriate

The fixtures can be used in tests like:

```python
async def test_task_creation(mock_task_service, test_config):
    task_id = await mock_task_service.create_task('scrape', test_config)
    assert task_id is not None
    status = await mock_task_service.get_task_status(task_id)
    assert status == 'pending'