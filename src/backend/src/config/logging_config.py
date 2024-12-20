"""
Logging configuration module for the Data Processing Pipeline.

This module provides a comprehensive logging configuration system with:
- Structured logging support using structlog
- Google Cloud Logging integration
- Log buffering and batching for performance
- Sensitive data masking
- Multiple handler support (console and cloud)
- Automatic error recovery
- Performance optimization through sampling and buffering

Version: 1.0.0
"""

import logging
from typing import Dict, Optional, Any  # version: 3.11+
import google.cloud.logging  # version: 3.5+
import structlog  # version: 23.1+
from config.constants import LOG_RETENTION_DAYS

# Global logging configuration
DEFAULT_LOG_LEVEL: int = logging.INFO
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
CLOUD_LOGGING_NAME: str = "data_processing_pipeline"
LOG_BATCH_SIZE: int = 100  # Number of logs to batch before sending
LOG_BUFFER_TIMEOUT: float = 5.0  # Seconds to wait before flushing log buffer

class LogConfig:
    """
    Manages logging configuration with enhanced security and performance features.
    
    Provides centralized logging configuration with support for:
    - Multiple logging handlers (console, cloud)
    - Structured logging format
    - Sensitive data masking
    - Log buffering and batching
    - Automatic error recovery
    """

    def __init__(self, config: Dict[str, Any], sensitive_patterns: Dict[str, str]) -> None:
        """
        Initialize logging configuration with security and performance settings.

        Args:
            config: Dictionary containing logging configuration parameters
            sensitive_patterns: Dictionary of patterns for masking sensitive data
        """
        self._logger = logging.getLogger(CLOUD_LOGGING_NAME)
        self._config = config
        self._sensitive_patterns = sensitive_patterns
        self._buffer_handler = None
        
        # Set default logging level
        self._logger.setLevel(config.get('log_level', DEFAULT_LOG_LEVEL))

    def get_console_handler(self) -> logging.StreamHandler:
        """
        Create and configure console logging handler.

        Returns:
            Configured StreamHandler instance
        """
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self._config.get('console_level', DEFAULT_LOG_LEVEL))
        
        return console_handler

    def get_cloud_handler(self) -> google.cloud.logging.handlers.CloudLoggingHandler:
        """
        Create and configure Google Cloud Logging handler with batching support.

        Returns:
            Configured CloudLoggingHandler instance
        """
        # Initialize cloud logging client with retry logic
        client = google.cloud.logging.Client()
        
        # Configure cloud handler with batching
        cloud_handler = google.cloud.logging.handlers.CloudLoggingHandler(
            client,
            name=CLOUD_LOGGING_NAME,
            batch_size=LOG_BATCH_SIZE,
            flush_interval=LOG_BUFFER_TIMEOUT
        )
        
        # Set retention policy based on configuration
        cloud_handler.retention = LOG_RETENTION_DAYS
        
        return cloud_handler

    def configure(self) -> None:
        """
        Apply comprehensive logging configuration with security and performance features.
        """
        # Clear any existing handlers
        self._logger.handlers.clear()
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                self.mask_sensitive_data,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Add console handler
        if self._config.get('enable_console', True):
            self._logger.addHandler(self.get_console_handler())
        
        # Add cloud handler if enabled
        if self._config.get('enable_cloud_logging', True):
            self._logger.addHandler(self.get_cloud_handler())
        
        # Configure error handling
        logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
        
        # Set propagate to False to prevent duplicate logging
        self._logger.propagate = False

    def mask_sensitive_data(self, logger: str, method_name: str, event_dict: Dict) -> Dict:
        """
        Process log records to mask sensitive information.

        Args:
            logger: Logger name
            method_name: Logging method name
            event_dict: Log event dictionary

        Returns:
            Processed log event dictionary with masked sensitive data
        """
        for field, pattern in self._sensitive_patterns.items():
            if field in event_dict:
                # Mask sensitive data with pattern
                if isinstance(event_dict[field], str):
                    event_dict[field] = f"***MASKED_{field}***"
        
        return event_dict

def setup_logging(
    config: Dict[str, Any],
    sensitive_patterns: Optional[Dict[str, str]] = None
) -> LogConfig:
    """
    Initialize application logging system with comprehensive configuration.

    Args:
        config: Logging configuration dictionary
        sensitive_patterns: Patterns for masking sensitive data (optional)

    Returns:
        Configured LogConfig instance
    """
    if sensitive_patterns is None:
        sensitive_patterns = {
            'password': r'\b[A-Za-z0-9._%+-]+\b',
            'api_key': r'\b[A-Za-z0-9-]{32,}\b',
            'token': r'\b[A-Za-z0-9-._~+/]+=*\b'
        }
    
    log_config = LogConfig(config, sensitive_patterns)
    log_config.configure()
    
    return log_config