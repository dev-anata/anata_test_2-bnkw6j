"""
Configuration package initialization module for the Data Processing Pipeline.

This module initializes and exports the configuration package, providing centralized access
to application settings, logging configuration, and environment-specific configurations.
Implements secure configuration management with validation, caching, and monitoring.

Version: 1.0.0
"""

from typing import Dict, Any, Optional  # version: 3.11+
from functools import wraps  # version: 3.11+
import threading
from logging import getLogger  # version: 3.11+

# Internal imports
from config.settings import settings, env, debug
from config.app_config import AppConfig, load_config
from config.logging_config import LogConfig, setup_logging

# Initialize logger
logger = getLogger(__name__)

# Thread-safe configuration cache
class ThreadSafeDict:
    """Thread-safe dictionary for storing configuration values."""
    
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value with thread safety."""
        with self._lock:
            return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set value with thread safety."""
        with self._lock:
            self._data[key] = value
    
    def clear(self) -> None:
        """Clear cache with thread safety."""
        with self._lock:
            self._data.clear()

# Global configuration cache
_config_cache = ThreadSafeDict()

def validate_config(func):
    """
    Decorator to validate configuration integrity.
    
    Args:
        func: Function to wrap with validation
        
    Returns:
        Wrapped function with configuration validation
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Validate required configuration is present
            if not isinstance(result, AppConfig):
                raise ValueError("Invalid configuration instance")
            # Validate critical settings
            if result.env == "production":
                if not result.storage_config.encryption.get("enabled"):
                    raise ValueError("Encryption must be enabled in production")
                if not result.logging_config.structured:
                    raise ValueError("Structured logging required in production")
            return result
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            raise
    return wrapper

def audit_config_access(func):
    """
    Decorator to audit configuration access.
    
    Args:
        func: Function to wrap with auditing
        
    Returns:
        Wrapped function with access auditing
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            logger.info(
                "Configuration accessed",
                extra={
                    "env": env,
                    "config_version": getattr(result, "config_version", "unknown")
                }
            )
            return result
        except Exception as e:
            logger.error(f"Configuration access failed: {str(e)}")
            raise
    return wrapper

@validate_config
@audit_config_access
def initialize_config(config_override: Optional[Dict[str, Any]] = None) -> AppConfig:
    """
    Initialize all configuration components with enhanced security, validation, and caching.
    
    Args:
        config_override: Optional configuration overrides
        
    Returns:
        Initialized application configuration instance with security controls
        
    Raises:
        ValueError: If configuration validation fails
        RuntimeError: If initialization fails
    """
    try:
        # Check cache first
        cached_config = _config_cache.get("app_config")
        if cached_config is not None:
            return cached_config
        
        # Initialize base configuration
        config = load_config(config_override)
        
        # Set up logging with security controls
        logging_config = config.get_logging_config()
        setup_logging(
            logging_config,
            sensitive_patterns={
                "password": r"\b[A-Za-z0-9._%+-]+\b",
                "api_key": r"\b[A-Za-z0-9-]{32,}\b",
                "token": r"\b[A-Za-z0-9-._~+/]+=*\b"
            }
        )
        
        # Cache the configuration
        _config_cache.set("app_config", config)
        
        logger.info(
            "Configuration initialized successfully",
            extra={
                "env": env,
                "config_version": config.config_version
            }
        )
        
        return config
        
    except Exception as e:
        logger.error(f"Configuration initialization failed: {str(e)}")
        raise RuntimeError(f"Failed to initialize configuration: {str(e)}")

# Initialize global configuration instance
config = initialize_config()

# Export package interface
__all__ = [
    "settings",
    "env",
    "debug",
    "config",
    "initialize_config"
]