"""
Root package initializer for the Data Processing Pipeline backend application.

This module initializes and configures the core application components including:
- Environment configuration
- Logging setup
- Core service initialization
- API configuration

Version: 1.0.0
"""

from typing import Dict, Optional, Any
import structlog

from config.app_config import AppConfig
from api.server import app

# Package metadata
__version__ = "1.0.0"
__author__ = "Data Processing Pipeline Team"

# Global application configuration
__app_config: Optional[AppConfig] = None

def initialize_app(config_override: Optional[Dict[str, Any]] = None) -> AppConfig:
    """
    Initialize the application with configuration and core components.
    
    This function performs the following initialization steps:
    1. Creates AppConfig instance with provided overrides
    2. Initializes application configuration
    3. Sets up logging based on environment
    4. Configures API settings
    5. Stores configuration in global __app_config
    
    Args:
        config_override: Optional dictionary containing configuration overrides
        
    Returns:
        AppConfig: Initialized application configuration
        
    Raises:
        RuntimeError: If initialization fails
    """
    global __app_config
    
    try:
        # Initialize structured logger
        logger = structlog.get_logger(__name__)
        logger.info("Initializing application")
        
        # Create AppConfig instance
        config = AppConfig(config_override)
        
        # Store global configuration
        __app_config = config
        
        # Log initialization status
        logger.info(
            "Application initialized",
            environment=config.env,
            debug=config.debug,
            version=__version__
        )
        
        return config
        
    except Exception as e:
        logger.error(
            "Application initialization failed",
            error=str(e),
            config_override=config_override
        )
        raise RuntimeError(f"Failed to initialize application: {str(e)}")

def get_app_config() -> AppConfig:
    """
    Get the current application configuration.
    
    Returns:
        AppConfig: Current application configuration instance
        
    Raises:
        RuntimeError: If application is not initialized
    """
    if __app_config is None:
        raise RuntimeError(
            "Application not initialized. Call initialize_app() first."
        )
    return __app_config

# Export public interface
__all__ = [
    '__version__',
    '__author__',
    'initialize_app',
    'get_app_config',
    'app'  # FastAPI application instance
]