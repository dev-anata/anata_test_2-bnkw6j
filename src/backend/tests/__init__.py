"""
Test package initializer for the Data Processing Pipeline test suite.

Configures the testing environment, sets up test markers, and exposes core testing
utilities and mock implementations. Ensures consistent test execution across the suite.

Version: 1.0.0
"""

import logging
import os
import sys
from typing import Dict, Any

import pytest  # version: 7.4+
import structlog  # version: 23.1+

from tests.utils.mocks import (
    MockTaskService,
    MockTaskRepository,
    create_mock_task,
    create_mock_execution
)
from config.settings import settings

# Test package metadata
TEST_PACKAGE_VERSION = "1.0.0"
TEST_PACKAGE_NAME = "data-processing-pipeline-tests"

# Configure structured logging for tests
logger = structlog.get_logger(__name__)

def configure_test_environment() -> None:
    """
    Configure the test environment with required settings and markers.
    
    Sets up test infrastructure including:
    - Environment variables
    - Pytest markers
    - Logging configuration
    - Test isolation
    - Async support
    """
    try:
        # Set test environment variables
        os.environ["ENV"] = "test"
        os.environ["DEBUG"] = "true"
        
        # Configure test logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("test.log")
            ]
        )

        # Register custom test markers
        pytest.register_assert_rewrite("tests.utils.assertions")
        
        # Register custom markers
        pytest.mark.integration = pytest.mark.integration
        pytest.mark.asyncio = pytest.mark.asyncio
        pytest.mark.slow = pytest.mark.slow
        pytest.mark.dependency = pytest.mark.dependency
        
        # Configure pytest-asyncio
        pytest_plugins = ["pytest_asyncio"]
        
        # Verify pytest version compatibility
        pytest_version = tuple(map(int, pytest.__version__.split(".")))
        if pytest_version < (7, 4):
            raise ImportError(
                f"Pytest version {pytest.__version__} is not supported. "
                f"Please upgrade to version 7.4 or higher."
            )
            
        # Set up test isolation
        os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8681"
        os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8682"
        
        # Configure test timeouts
        pytest.ini_options = {
            "asyncio_mode": "auto",
            "timeout": 300,
            "timeout_method": "thread"
        }
        
        logger.info(
            "Test environment configured",
            package_name=TEST_PACKAGE_NAME,
            version=TEST_PACKAGE_VERSION,
            pytest_version=pytest.__version__
        )

    except Exception as e:
        logger.error(
            "Failed to configure test environment",
            error=str(e),
            package_name=TEST_PACKAGE_NAME
        )
        raise

# Configure test environment on import
configure_test_environment()

# Export test utilities and mocks
__all__ = [
    'MockTaskService',
    'MockTaskRepository', 
    'create_mock_task',
    'create_mock_execution',
    'configure_test_environment',
    'TEST_PACKAGE_VERSION',
    'TEST_PACKAGE_NAME'
]