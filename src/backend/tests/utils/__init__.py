"""
Test utilities package initialization module.

This module exports commonly used testing utilities, mocks, fixtures, and factories
for testing the data processing pipeline components. It provides a centralized access
point for test infrastructure with comprehensive type hints and security controls.

Version: 1.0.0
"""

import logging  # version: 3.11+
from typing import Optional  # version: 3.11+

# Import mock implementations
from tests.utils.mocks import (
    MockTaskRepository,
    MockTaskService,
    create_mock_task,
    create_mock_execution
)

# Import test fixtures
from tests.utils.fixtures import (
    create_test_task,
    create_test_execution,
    create_test_data_object,
    create_test_data_batch,
    cleanup_test_data
)

# Import test factories
from tests.utils.factories import (
    TaskFactory,
    TaskExecutionFactory,
    DataObjectFactory
)

# Configure package-level logger
logger = logging.getLogger(__name__)

def setup_test_logging(log_level: str = "INFO") -> None:
    """
    Configure logging for test utilities with proper formatting and level.
    
    Args:
        log_level: Desired logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Configure logging format for tests
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set package logger level
    logger.setLevel(log_level)
    
    logger.debug("Test logging configured", extra={"log_level": log_level})

# Export commonly used test utilities
__all__ = [
    # Mock implementations
    'MockTaskRepository',
    'MockTaskService',
    'create_mock_task',
    'create_mock_execution',
    
    # Test fixtures
    'create_test_task',
    'create_test_execution', 
    'create_test_data_object',
    'create_test_data_batch',
    'cleanup_test_data',
    
    # Test factories
    'TaskFactory',
    'TaskExecutionFactory',
    'DataObjectFactory',
    
    # Utility functions
    'setup_test_logging'
]

# Configure default logging
setup_test_logging()