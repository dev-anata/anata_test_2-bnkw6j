"""
Enhanced structured logging system with cloud integration and security features.

This module implements a comprehensive logging system with:
- Structured JSON logging
- Google Cloud Logging integration
- Secure data handling and masking
- Performance optimization through buffering
- Trace context support
- Automatic retries for cloud operations

Version: 1.0.0
"""

import logging
import re
import time
from typing import Dict, Optional, Any, List, Union  # version: 3.11+
from functools import wraps
import structlog  # version: 23.1+
from google.cloud import logging as cloud_logging  # version: 3.5+
from google.api_core import retry  # version: 3.5+

from config.logging_config import LogConfig
from config.settings import settings

# Global constants
DEFAULT_LOG_LEVEL = logging.INFO
TRACE_ID_KEY = 'trace_id'
SPAN_ID_KEY = 'span_id'
SENSITIVE_PATTERNS = [r'password', r'token', r'key', r'secret']
MAX_RETRIES = 3
RETRY_DELAY = 1.0

class Logger:
    """
    Enhanced structured logger with cloud integration, buffering, and security features.
    
    Features:
    - Structured JSON logging
    - Secure data masking
    - Cloud logging integration
    - Performance optimization through buffering
    - Trace context support
    - Automatic retries
    """

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        buffer_size: Optional[int] = None
    ) -> None:
        """
        Initialize logger with enhanced configuration.

        Args:
            name: Logger name
            context: Initial context dictionary
            buffer_size: Size of log buffer (defaults to settings)
        """
        # Initialize structlog logger
        self._logger = structlog.get_logger(name)
        
        # Initialize context with trace information
        self._context = context or {}
        if TRACE_ID_KEY not in self._context:
            self._context[TRACE_ID_KEY] = None
        if SPAN_ID_KEY not in self._context:
            self._context[SPAN_ID_KEY] = None
            
        # Configure buffering
        self._buffer_size = buffer_size or settings.log_buffer_size
        self._buffer: List[Dict[str, Any]] = []
        
        # Configure cloud logging if in production
        if not settings.debug:
            self._setup_cloud_logging()

    def _setup_cloud_logging(self) -> None:
        """Configure Google Cloud Logging with retry mechanism."""
        try:
            client = cloud_logging.Client()
            self._cloud_logger = client.logger(settings.env)
        except Exception as e:
            self._logger.error("Failed to initialize cloud logging", error=str(e))
            self._cloud_logger = None

    def _mask_sensitive_data(self, data: Union[str, Dict]) -> Union[str, Dict]:
        """
        Mask sensitive information in logs.

        Args:
            data: Input string or dictionary to mask

        Returns:
            Masked data with sensitive information hidden
        """
        if isinstance(data, str):
            masked = data
            for pattern in SENSITIVE_PATTERNS:
                masked = re.sub(
                    f'{pattern}["\']?\s*[:=]\s*["\']?[^"\'\s]+["\']?',
                    f'{pattern}=***MASKED***',
                    masked,
                    flags=re.IGNORECASE
                )
            return masked
        elif isinstance(data, dict):
            return {
                k: '***MASKED***' if any(p in k.lower() for p in SENSITIVE_PATTERNS)
                else self._mask_sensitive_data(v) if isinstance(v, (str, dict))
                else v
                for k, v in data.items()
            }
        return data

    @retry.Retry(
        predicate=retry.if_exception_type(Exception),
        initial=RETRY_DELAY,
        maximum=RETRY_DELAY * 4,
        multiplier=2,
        deadline=30.0
    )
    def _write_to_cloud(self, log_dict: Dict[str, Any]) -> None:
        """
        Write log to Google Cloud Logging with retry mechanism.

        Args:
            log_dict: Log entry dictionary
        """
        if self._cloud_logger:
            try:
                self._cloud_logger.log_struct(
                    log_dict,
                    severity=log_dict.get('level', 'INFO')
                )
            except Exception as e:
                self._logger.error(
                    "Failed to write to cloud logging",
                    error=str(e),
                    retry_count=0
                )

    def bind_context(self, context: Dict[str, Any]) -> 'Logger':
        """
        Bind additional context with security checks.

        Args:
            context: Context dictionary to bind

        Returns:
            Self reference with updated context
        """
        # Mask sensitive data in context
        safe_context = self._mask_sensitive_data(context)
        
        # Update context
        self._context.update(safe_context)
        self._logger = self._logger.bind(**safe_context)
        
        return self

    def _prepare_log_entry(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare log entry with context and security measures.

        Args:
            level: Log level
            message: Log message
            extra: Additional context

        Returns:
            Prepared log entry dictionary
        """
        # Mask sensitive data
        safe_message = self._mask_sensitive_data(message)
        safe_extra = self._mask_sensitive_data(extra or {})
        
        # Prepare log entry
        log_entry = {
            'timestamp': time.time(),
            'level': level,
            'message': safe_message,
            'logger': self._logger.name,
            **self._context,
            **safe_extra
        }
        
        return log_entry

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """
        Log message at INFO level with buffering.

        Args:
            message: Log message
            extra: Additional context
        """
        log_entry = self._prepare_log_entry('INFO', message, extra)
        
        # Add to buffer
        self._buffer.append(log_entry)
        
        # Flush if buffer is full
        if len(self._buffer) >= self._buffer_size:
            self.flush_buffer()
        
        # Always log to structlog
        self._logger.info(message, **log_entry)

    def error(
        self,
        message: str,
        exc: Optional[Exception] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enhanced error logging with exception handling.

        Args:
            message: Error message
            exc: Exception object
            extra: Additional context
        """
        # Add exception information
        error_context = extra or {}
        if exc:
            error_context.update({
                'error_type': type(exc).__name__,
                'error_message': str(exc),
                'stack_trace': logging.format_exc() if logging.format_exc() else None
            })
        
        log_entry = self._prepare_log_entry('ERROR', message, error_context)
        
        # Force flush buffer for errors
        self._buffer.append(log_entry)
        self.flush_buffer()
        
        # Log to structlog
        self._logger.error(message, **log_entry)

    def flush_buffer(self) -> None:
        """Flush buffered logs to output."""
        if not self._buffer:
            return
            
        # Process buffered logs
        for log_entry in self._buffer:
            if not settings.debug:
                self._write_to_cloud(log_entry)
        
        # Clear buffer
        self._buffer.clear()

def get_logger(
    name: str,
    context: Optional[Dict[str, Any]] = None,
    buffer_size: Optional[int] = None
) -> Logger:
    """
    Create and configure a logger instance with security features.

    Args:
        name: Logger name
        context: Initial context dictionary
        buffer_size: Size of log buffer

    Returns:
        Configured logger instance
    """
    return Logger(name, context, buffer_size)

def configure_logging() -> None:
    """Initialize logging system with enhanced features."""
    # Configure logging based on environment
    config = {
        'log_level': logging.DEBUG if settings.debug else logging.INFO,
        'enable_console': True,
        'enable_cloud_logging': not settings.debug
    }
    
    # Initialize logging configuration
    log_config = LogConfig(config, {
        pattern: '***MASKED***' for pattern in SENSITIVE_PATTERNS
    })
    
    # Apply configuration
    log_config.configure()