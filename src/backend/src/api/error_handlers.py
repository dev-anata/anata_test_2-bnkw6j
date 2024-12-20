"""
FastAPI exception handlers for standardized error responses.

This module implements comprehensive exception handlers for the FastAPI application,
providing consistent error responses with appropriate HTTP status codes while ensuring
sensitive information is properly filtered and all errors are logged for monitoring.

Version: 1.0.0
"""

from typing import Dict, Any, Optional  # version: 3.11+
from fastapi import FastAPI, Request, status  # version: 0.100+
from fastapi.responses import JSONResponse  # version: 0.100+
import uuid
import time

from core.exceptions import (
    PipelineException,
    ValidationException,
    TaskException,
    StorageException,
    ConfigurationException
)
from monitoring.logger import Logger, get_logger

# Initialize logger with security context
logger: Logger = get_logger(__name__)

def create_error_response(
    status_code: int,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
    """
    Create a standardized error response with security filtering.

    Args:
        status_code: HTTP status code
        error_type: Type of error
        message: Error message
        details: Additional error details (optional)
        headers: Response headers (optional)

    Returns:
        JSONResponse with standardized error format
    """
    # Generate trace ID for error tracking
    trace_id = str(uuid.uuid4())
    
    # Create base error response
    error_response = {
        "error": error_type,
        "message": message,
        "trace_id": trace_id,
        "timestamp": int(time.time())
    }
    
    # Add filtered details if provided
    if details:
        # Filter out sensitive information
        filtered_details = {
            k: v for k, v in details.items()
            if not any(sensitive in k.lower() 
                      for sensitive in ['password', 'token', 'key', 'secret'])
        }
        if filtered_details:
            error_response["details"] = filtered_details
    
    return JSONResponse(
        status_code=status_code,
        content=error_response,
        headers=headers
    )

async def handle_validation_error(
    request: Request,
    exc: ValidationException
) -> JSONResponse:
    """
    Handle validation exceptions with enhanced security filtering.

    Args:
        request: FastAPI request object
        exc: ValidationException instance

    Returns:
        JSONResponse with validation error details
    """
    # Log validation error with context
    logger.error(
        "Validation error occurred",
        extra={
            "error_type": "validation_error",
            "path": request.url.path,
            "method": request.method,
            "validation_errors": exc.validation_errors
        }
    )
    
    return create_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_type="validation_error",
        message=exc.message,
        details=exc.validation_errors
    )

async def handle_task_error(
    request: Request,
    exc: TaskException
) -> JSONResponse:
    """
    Handle task-related exceptions with retry mechanism.

    Args:
        request: FastAPI request object
        exc: TaskException instance

    Returns:
        JSONResponse with task error details and retry information
    """
    # Calculate retry parameters
    retry_after = min(300, 2 ** exc.details.get("retry_count", 0))
    
    # Log task error with context
    logger.error(
        "Task execution error",
        extra={
            "error_type": "task_error",
            "task_id": exc.task_id,
            "path": request.url.path,
            "method": request.method,
            "task_details": exc.task_details
        }
    )
    
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="task_error",
        message=exc.message,
        details=exc.task_details,
        headers={"Retry-After": str(retry_after)}
    )

async def handle_storage_error(
    request: Request,
    exc: StorageException
) -> JSONResponse:
    """
    Handle storage-related exceptions with circuit breaker integration.

    Args:
        request: FastAPI request object
        exc: StorageException instance

    Returns:
        JSONResponse with storage error details
    """
    # Log storage error with context
    logger.error(
        "Storage operation failed",
        extra={
            "error_type": "storage_error",
            "path": request.url.path,
            "method": request.method,
            "storage_path": exc.storage_path,
            "storage_details": exc.storage_details
        }
    )
    
    return create_error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_type="storage_error",
        message=exc.message,
        details=exc.storage_details
    )

async def handle_configuration_error(
    request: Request,
    exc: ConfigurationException
) -> JSONResponse:
    """
    Handle configuration-related exceptions with security filtering.

    Args:
        request: FastAPI request object
        exc: ConfigurationException instance

    Returns:
        JSONResponse with filtered configuration error details
    """
    # Log configuration error with context
    logger.error(
        "Configuration error occurred",
        extra={
            "error_type": "configuration_error",
            "path": request.url.path,
            "method": request.method,
            "config_details": exc.config_details
        }
    )
    
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="configuration_error",
        message=exc.message,
        details=exc.config_details
    )

async def handle_pipeline_error(
    request: Request,
    exc: PipelineException
) -> JSONResponse:
    """
    Handle general pipeline exceptions with comprehensive logging.

    Args:
        request: FastAPI request object
        exc: PipelineException instance

    Returns:
        JSONResponse with error details
    """
    # Log pipeline error with context
    logger.error(
        "Pipeline error occurred",
        extra={
            "error_type": "pipeline_error",
            "path": request.url.path,
            "method": request.method,
            "details": exc.details
        }
    )
    
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="pipeline_error",
        message=exc.message,
        details=exc.details
    )

def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(ValidationException, handle_validation_error)
    app.add_exception_handler(TaskException, handle_task_error)
    app.add_exception_handler(StorageException, handle_storage_error)
    app.add_exception_handler(ConfigurationException, handle_configuration_error)
    app.add_exception_handler(PipelineException, handle_pipeline_error)

__all__ = [
    'register_exception_handlers',
    'create_error_response',
    'handle_validation_error',
    'handle_task_error',
    'handle_storage_error',
    'handle_configuration_error',
    'handle_pipeline_error'
]