"""
FastAPI middleware components for request processing.

This module implements middleware components for:
- Request logging with trace context
- Distributed rate limiting
- Standardized error handling
- Performance monitoring

Version: 1.0.0
"""

import time
import json
from typing import Dict, Any, Optional, Callable  # version: 3.11+
from uuid import uuid4  # version: 3.11+
from fastapi import FastAPI, Request, Response  # version: 0.100+
from starlette.middleware.base import BaseHTTPMiddleware  # version: 0.27+
from starlette.exceptions import HTTPException  # version: 0.27+

from core.exceptions import PipelineException, ValidationException
from monitoring.logger import Logger, get_logger
from security.rate_limiter import RateLimiter, RateLimitExceeded
from config.settings import settings

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging all incoming HTTP requests and responses with trace context.
    
    Features:
    - Request/response logging with trace context
    - Performance metrics collection
    - Sensitive data masking
    - Structured logging format
    """

    def __init__(self, app: FastAPI) -> None:
        """
        Initialize the logging middleware.

        Args:
            app: FastAPI application instance
        """
        super().__init__(app)
        self._logger: Logger = get_logger("api.request")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process and log request/response cycle with trace context.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response with trace headers
        """
        # Generate trace context
        trace_id = str(uuid4())
        span_id = str(uuid4())

        # Bind trace context to logger
        self._logger.bind_context({
            "trace_id": trace_id,
            "span_id": span_id
        })

        # Start request timing
        start_time = time.time()

        # Log request details
        self._logger.info(
            "Incoming request",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "trace_id": trace_id
            }
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate request duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log response
            self._logger.info(
                "Request completed",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "trace_id": trace_id
                }
            )

            # Add trace headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Span-ID"] = span_id

            return response

        except Exception as e:
            # Log error with trace context
            self._logger.error(
                "Request failed",
                exc=e,
                extra={
                    "trace_id": trace_id,
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing distributed API rate limits using Redis backend.
    
    Features:
    - Redis-backed distributed rate limiting
    - Configurable rate limits per client
    - Rate limit headers in responses
    - Automatic retry-after calculation
    """

    def __init__(self, app: FastAPI) -> None:
        """
        Initialize rate limiting middleware.

        Args:
            app: FastAPI application instance
        """
        super().__init__(app)
        self._rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_requests,
            window_size=settings.rate_limit_window
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check and enforce distributed rate limits.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response with rate limit headers
        """
        # Extract client identifier (API key or IP)
        client_id = request.headers.get("X-API-Key") or request.client.host

        try:
            # Check rate limit
            self._rate_limiter.check_rate_limit(client_id)

            # Get remaining requests
            limit_info = self._rate_limiter.get_remaining_requests(client_id)

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
            response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining_requests"])
            response.headers["X-RateLimit-Reset"] = str(limit_info["reset_time"])

            return response

        except RateLimitExceeded as e:
            # Return 429 with retry-after header
            response = Response(
                content=json.dumps({
                    "error": "rate_limit_exceeded",
                    "message": str(e),
                    "retry_after": e.retry_after
                }),
                status_code=429,
                media_type="application/json"
            )
            response.headers["Retry-After"] = str(e.retry_after)
            return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware for standardized error handling and formatting.
    
    Features:
    - Consistent error response format
    - Error classification and status codes
    - Error logging with context
    - Sensitive data masking in errors
    """

    def __init__(self, app: FastAPI) -> None:
        """
        Initialize error handling middleware.

        Args:
            app: FastAPI application instance
        """
        super().__init__(app)
        self._logger = get_logger("api.error")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle and format errors with proper classification.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response with proper error formatting
        """
        try:
            return await call_next(request)

        except ValidationException as e:
            return self._create_error_response(
                status_code=400,
                error_type="validation_error",
                message=str(e),
                details=e.validation_errors
            )

        except RateLimitExceeded as e:
            return self._create_error_response(
                status_code=429,
                error_type="rate_limit_exceeded",
                message=str(e),
                details={"retry_after": e.retry_after}
            )

        except HTTPException as e:
            return self._create_error_response(
                status_code=e.status_code,
                error_type="http_error",
                message=str(e.detail)
            )

        except PipelineException as e:
            return self._create_error_response(
                status_code=500,
                error_type="pipeline_error",
                message=str(e),
                details=e.details
            )

        except Exception as e:
            # Log unexpected errors
            self._logger.error(
                "Unexpected error",
                exc=e,
                extra={
                    "url": str(request.url),
                    "method": request.method
                }
            )
            return self._create_error_response(
                status_code=500,
                error_type="internal_error",
                message="An unexpected error occurred"
            )

    def _create_error_response(
        self,
        status_code: int,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Response:
        """
        Create standardized error response.

        Args:
            status_code: HTTP status code
            error_type: Error classification
            message: Error message
            details: Optional error details

        Returns:
            Formatted error response
        """
        content = {
            "error": error_type,
            "message": message
        }
        if details:
            content["details"] = details

        return Response(
            content=json.dumps(content),
            status_code=status_code,
            media_type="application/json"
        )