"""
Unit test initialization module for the Data Processing Pipeline.

This module configures the test environment for unit testing, including test markers,
isolation settings, mock services, and test result reporting. It ensures proper test
categorization and resource management for the CI/CD pipeline.

Version: 1.0.0
"""

import logging  # version: 3.11+
import pytest  # version: 7.4+
import structlog  # version: 23.1+
from typing import List, Dict, Any  # version: 3.11+

from tests.conftest import pytest_configure
from tests.utils.mocks import MockTaskService, MockTaskRepository

# Configure structured logger for unit tests
LOGGER = structlog.get_logger(__name__)

# Define available unit test markers for test categorization
UNIT_TEST_MARKERS: List[str] = [
    'api',          # API endpoint tests
    'services',     # Service layer tests
    'models',       # Data model tests
    'repositories', # Repository tests
    'security',     # Security feature tests
    'tasks',        # Task processing tests
    'error_handling', # Error handling tests
    'performance',  # Performance-related tests
    'integration'   # Integration point tests
]

def configure_unit_tests() -> None:
    """
    Configure pytest settings specific to unit tests.
    
    This function sets up the test environment with appropriate settings for
    unit testing, including test isolation, mock services, and reporting.
    """
    try:
        # Register unit test markers
        for marker in UNIT_TEST_MARKERS:
            pytest.mark.marker = pytest.mark.marker

        # Configure test isolation settings
        pytest.mark.filterwarnings("error")  # Treat warnings as errors
        pytest.mark.asyncio.apply_to_all = True  # Enable async test support

        # Set up mock service defaults
        MockTaskService._default_config = {
            "source": "test-source",
            "parameters": {
                "test_mode": True,
                "timeout": 30,
                "retries": 1
            }
        }

        # Configure test logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        LOGGER.info("Configured unit test environment")

        # Configure test coverage settings
        pytest.mark.coverage = {
            "branch": True,
            "source": ["src"],
            "omit": ["tests/*", "**/__init__.py"],
            "fail_under": 80
        }

        # Set up error handling configuration
        pytest.mark.error_handling = {
            "raise_on_unhandled": True,
            "capture_warnings": True
        }

        # Initialize resource cleanup handlers
        pytest.mark.autouse = True
        pytest.mark.usefixtures("cleanup_after_test")

        # Configure parallel test execution
        pytest.mark.xdist = {
            "numprocesses": "auto",
            "maxprocesses": 4
        }

        # Set up test result reporting for CI/CD
        pytest.mark.report = {
            "junit_family": "xunit2",
            "junit_suite_name": "unit_tests",
            "verbose": 2
        }

        LOGGER.info(
            "Unit test configuration complete",
            markers=UNIT_TEST_MARKERS,
            coverage_threshold=80
        )

    except Exception as e:
        LOGGER.error(
            "Failed to configure unit tests",
            error=str(e),
            markers=UNIT_TEST_MARKERS
        )
        raise

# Export module components
__all__ = [
    'configure_unit_tests',
    'UNIT_TEST_MARKERS',
    'MockTaskService',
    'MockTaskRepository'
]