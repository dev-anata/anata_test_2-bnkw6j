"""
System-wide constants used across the Data Processing Pipeline application.

This module defines constant values that control various aspects of the system including:
- API configuration and versioning
- Timeouts and retry policies
- Rate limiting parameters
- Security settings
- Storage configuration
- Pagination settings
- Monitoring configuration

These constants ensure consistent behavior across all system components and provide
centralized control over key system parameters.

Version: 1.0
"""

from typing import Final  # version: 3.11+

# API Configuration
API_VERSION: Final[str] = "v1"

# Operation Timeouts and Retries
DEFAULT_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes timeout for API operations
MAX_RETRIES: Final[int] = 3  # Maximum number of retry attempts for failed operations
RETRY_BACKOFF_FACTOR: Final[int] = 2  # Exponential backoff multiplier between retries

# Rate Limiting Configuration
API_RATE_LIMIT_MAX_REQUESTS: Final[int] = 1000  # Maximum requests per window
API_RATE_LIMIT_WINDOW_SIZE: Final[int] = 3600  # Window size in seconds (1 hour)

# Security Configuration
TOKEN_EXPIRATION_SECONDS: Final[int] = 3600  # JWT token expiration (1 hour)
API_KEY_LENGTH: Final[int] = 32  # Length of API keys in bytes

# Storage Configuration
STORAGE_BUCKET_NAME: Final[str] = "data-processing-pipeline"  # Default GCS bucket

# Pagination Settings
DEFAULT_PAGE_SIZE: Final[int] = 100  # Default items per page
MAX_PAGE_SIZE: Final[int] = 1000  # Maximum items per page

# Monitoring Configuration
LOG_RETENTION_DAYS: Final[int] = 90  # Days to retain system logs
METRIC_COLLECTION_INTERVAL: Final[int] = 60  # Metric collection interval in seconds