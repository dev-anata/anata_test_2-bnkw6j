"""
API routes initialization module for the Data Processing Pipeline.

This module aggregates and configures all API route modules with comprehensive
security controls, error handling, and monitoring. It provides centralized route
management for health checks, task management, data management, OCR processing,
scraping, status, and configuration endpoints.

Version: 1.0.0
"""

from typing import Dict, Any
import structlog  # version: 23.1+
from fastapi import APIRouter, Request, Response, HTTPException  # version: 0.100+
from fastapi.responses import JSONResponse

from api.routes.health import router as health_router
from api.routes.tasks import router as tasks_router
from api.routes.data import router as data_router
from api.routes.ocr import router as ocr_router
from api.routes.scraping import router as scraping_router
from api.routes.status import router as status_router
from api.routes.config import router as config_router
from monitoring.metrics import track_request_duration
from monitoring.logger import get_logger

# Initialize structured logger
logger = get_logger(__name__)

# Initialize main API router with version prefix
api_router = APIRouter(prefix="/api/v1", tags=["api"])

def initialize_router() -> APIRouter:
    """
    Initialize and configure the main API router with all subrouters and middleware.

    Returns:
        APIRouter: Configured API router with all routes registered
    """
    # Register all subrouters
    api_router.include_router(health_router, prefix="/health")
    api_router.include_router(tasks_router, prefix="/tasks")
    api_router.include_router(data_router, prefix="/data")
    api_router.include_router(ocr_router, prefix="/ocr")
    api_router.include_router(scraping_router, prefix="/scraping")
    api_router.include_router(status_router, prefix="/status")
    api_router.include_router(config_router, prefix="/config")

    # Register error handlers
    register_error_handlers(api_router)

    logger.info(
        "API router initialized",
        extra={
            "routes": [
                "health", "tasks", "data", "ocr",
                "scraping", "status", "config"
            ]
        }
    )

    return api_router

def register_error_handlers(router: APIRouter) -> None:
    """
    Register comprehensive error handlers for the API router.

    Args:
        router: FastAPI router to register handlers for
    """
    @router.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with detailed error responses."""
        logger.warning(
            "HTTP exception occurred",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path
            }
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "detail": exc.detail,
                "status_code": exc.status_code
            }
        )

    @router.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions with secure error responses."""
        logger.error(
            "Unexpected error occurred",
            exc=exc,
            extra={"path": request.url.path}
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred"
            }
        )

    @router.middleware("http")
    @track_request_duration(method="ALL", endpoint="*")
    async def add_security_headers(request: Request, call_next) -> Response:
        """Add security headers to all responses."""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response

    @router.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        """Log all API requests with performance tracking."""
        logger.info(
            "API request received",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None
            }
        )
        
        response = await call_next(request)
        
        logger.info(
            "API request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code
            }
        )
        
        return response

# Export configured router
__all__ = ["api_router"]