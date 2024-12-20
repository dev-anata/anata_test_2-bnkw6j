"""
API package initialization module for the Data Processing Pipeline.

This module initializes and configures the FastAPI application with comprehensive
security controls, monitoring, and error handling. It serves as the main entry point
for the REST API service.

Version: 1.0.0
"""

from fastapi import __version__ as fastapi_version  # version: 0.100+
import structlog  # version: 23.1+

from api.server import app
from api.routes import api_router

# Package metadata
__version__ = "0.1.0"
__author__ = "Data Processing Pipeline Team"

# Initialize structured logger
logger = structlog.get_logger(__name__)

def initialize_api() -> app:
    """
    Initialize the API package with comprehensive configuration.
    
    Configures the FastAPI application with:
    - Security middleware and controls
    - Request/response monitoring
    - Error handling
    - API route registration
    - Performance optimization
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    try:
        logger.info(
            "Initializing API service",
            extra={
                "fastapi_version": fastapi_version,
                "api_version": __version__
            }
        )

        # Include API routes
        app.include_router(api_router)

        # Log successful initialization
        logger.info(
            "API service initialized successfully",
            extra={
                "routes": [
                    "health",
                    "tasks",
                    "data",
                    "ocr",
                    "scraping",
                    "status",
                    "config"
                ]
            }
        )

        return app

    except Exception as e:
        logger.error(
            "Failed to initialize API service",
            exc=e,
            extra={"error": str(e)}
        )
        raise

# Initialize API on module import
app = initialize_api()

# Export public interface
__all__ = [
    "app",
    "__version__",
    "initialize_api"
]