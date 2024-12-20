"""
API security middleware and utilities for authentication, authorization, and rate limiting.

This module implements enterprise-grade security controls for the API layer including:
- API key validation
- JWT token authentication
- Rate limiting
- Security dependency injection

Version: 1.0.0
"""

from typing import Dict, Optional, Union  # version: 3.11+
from fastapi import HTTPException, Request  # version: 0.100+
from fastapi.security import HTTPBearer  # version: 0.100+
import logging  # version: 3.11+

from security.token_service import TokenService  # Internal import
from security.rate_limiter import RateLimiter, RateLimitExceeded  # Internal import
from config.settings import settings  # Internal import
from core.exceptions import PipelineException

# Initialize security components
security_scheme = HTTPBearer(scheme_name='Bearer')
token_service = TokenService()
rate_limiter = RateLimiter(
    settings.rate_limit_requests,
    settings.rate_limit_window
)

# Configure logging
logger = logging.getLogger(__name__)

class SecurityError(PipelineException):
    """
    Custom exception for security-related errors.

    Attributes:
        message (str): Human-readable error description
        status_code (int): HTTP status code to return
        headers (Optional[Dict]): Additional response headers
    """

    def __init__(self, message: str, status_code: int = 401, 
                 headers: Optional[Dict] = None) -> None:
        """Initialize security error with message and status code."""
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers or {}


async def verify_api_key(request: Request) -> str:
    """
    Verify API key from request headers.

    Args:
        request: FastAPI request object

    Returns:
        str: Validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    try:
        # Extract API key from headers
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise SecurityError(
                "Missing API key",
                status_code=401
            )

        # Validate API key against settings
        if api_key not in settings.API_KEYS:
            raise SecurityError(
                "Invalid API key",
                status_code=401
            )

        return api_key

    except SecurityError as e:
        logger.warning(f"API key validation failed: {str(e)}")
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
            headers=e.headers
        )
    except Exception as e:
        logger.error(f"Unexpected error in API key validation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during authentication"
        )


async def verify_token(token: str) -> Dict:
    """
    Verify JWT token and extract claims.

    Args:
        token: JWT token to verify

    Returns:
        Dict: Validated token claims

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Validate token and get claims
        claims = token_service.validate_token(token)
        return claims

    except Exception as e:
        logger.warning(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def check_rate_limit(request: Request) -> bool:
    """
    Check rate limit for client request.

    Args:
        request: FastAPI request object

    Returns:
        bool: True if within rate limit

    Raises:
        HTTPException: If rate limit is exceeded
    """
    try:
        # Get client identifier (API key or IP address)
        client_id = request.headers.get("X-API-Key")
        if not client_id:
            client_id = request.client.host

        # Check rate limit
        rate_limiter.check_rate_limit(client_id)

        # Get remaining requests for headers
        limit_info = rate_limiter.get_remaining_requests(client_id)
        
        # Add rate limit headers to response
        request.state.rate_limit_headers = {
            "X-RateLimit-Remaining": str(limit_info["remaining_requests"]),
            "X-RateLimit-Reset": str(limit_info["reset_time"])
        }

        return True

    except RateLimitExceeded as e:
        logger.warning(f"Rate limit exceeded for client {client_id}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(e.retry_after),
                "X-RateLimit-Reset": str(e.retry_after)
            }
        )
    except Exception as e:
        logger.error(f"Rate limiting error: {str(e)}")
        # Fail open on unexpected errors
        return True


class SecurityDependency:
    """
    FastAPI dependency for handling API security.

    Provides a reusable dependency that combines API key validation,
    rate limiting, and optional JWT token authentication.
    """

    def __init__(self) -> None:
        """Initialize security dependency with required services."""
        self._token_service = token_service
        self._rate_limiter = rate_limiter

    async def authenticate(self, request: Request) -> Dict[str, Union[str, Dict]]:
        """
        Authenticate and authorize request.

        Args:
            request: FastAPI request object

        Returns:
            Dict containing authentication context

        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Verify API key
            api_key = await verify_api_key(request)

            # Check rate limit
            await check_rate_limit(request)

            # Initialize auth context
            auth_context = {
                "api_key": api_key,
                "client_id": request.client.host,
                "token_claims": None
            }

            # Verify JWT token if present
            authorization = request.headers.get("Authorization")
            if authorization:
                scheme, token = authorization.split()
                if scheme.lower() == "bearer":
                    claims = await verify_token(token)
                    auth_context["token_claims"] = claims

            return auth_context

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error during authentication"
            )


# Export security components
__all__ = [
    'verify_api_key',
    'verify_token',
    'check_rate_limit',
    'SecurityDependency',
    'security_scheme'
]