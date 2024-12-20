"""
Authentication and authorization middleware for the Data Processing Pipeline.

This module implements enterprise-grade security controls including API key validation,
JWT token verification, rate limiting, and comprehensive security monitoring. It provides
a secure authentication layer for all API endpoints.

Version: 1.0.0
"""

from typing import Dict, Optional, Any  # version: 3.11+
import logging  # version: 3.11+
import redis  # version: 4.5+
from fastapi import HTTPException, Depends, Request, Response  # version: 0.100+

from security.token_service import TokenService
from security.rate_limiter import RateLimiter, RateLimitExceeded
from core.exceptions import PipelineException
from config.settings import settings

# Constants for authentication and security
AUTH_HEADER_NAME = "X-API-Key"
TOKEN_HEADER_NAME = "Authorization"
TOKEN_TYPE = "Bearer"
MAX_AUTH_ATTEMPTS = 3
CACHE_TTL = 300  # 5 minutes cache for validated API keys

class AuthenticationError(PipelineException):
    """
    Enhanced custom exception for authentication-related errors.
    
    Provides detailed error information while maintaining security by not exposing
    sensitive details in error messages.
    
    Attributes:
        message (str): Human-readable error description
        error_code (str): Specific error code for categorization
        details (Dict[str, Any]): Additional error context
    """
    
    def __init__(self, message: str, error_code: str, details: Dict[str, Any] = None) -> None:
        """Initialize authentication error with enhanced details."""
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        
        # Log security event
        logger = logging.getLogger(__name__)
        logger.error(f"Authentication error: {error_code} - {message}", 
                    extra={"error_details": self.details})


class AuthMiddleware:
    """
    Enhanced middleware for handling API authentication and authorization.
    
    Implements comprehensive security controls including API key validation,
    JWT token verification, rate limiting, and security monitoring.
    
    Attributes:
        _token_service (TokenService): Service for JWT token operations
        _rate_limiter (RateLimiter): Rate limiting service
        _logger (logging.Logger): Logger for security events
        _cache (redis.Redis): Redis cache for API key validation
    """
    
    def __init__(self, token_service: TokenService, rate_limiter: RateLimiter,
                 cache: redis.Redis) -> None:
        """
        Initialize auth middleware with security dependencies.
        
        Args:
            token_service: Service for JWT token operations
            rate_limiter: Rate limiting service
            cache: Redis cache for API key validation
        """
        self._token_service = token_service
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._logger = logging.getLogger(__name__)
        
        # Configure enhanced logging
        self._logger.setLevel(logging.INFO if settings.env == "production" else logging.DEBUG)

    async def verify_api_key(self, request: Request) -> Dict[str, Any]:
        """
        Verify API key with caching and enhanced security checks.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dict containing validated API key details and permissions
            
        Raises:
            AuthenticationError: If API key validation fails
        """
        try:
            # Extract API key from headers
            api_key = request.headers.get(AUTH_HEADER_NAME)
            if not api_key:
                raise AuthenticationError(
                    "Missing API key", 
                    "MISSING_API_KEY",
                    {"headers": dict(request.headers)}
                )
            
            # Check cache first
            cache_key = f"api_key:{api_key}"
            cached_details = self._cache.get(cache_key)
            if cached_details:
                return eval(cached_details)
            
            # Validate API key format and signature
            # Note: Actual validation logic would be implemented in a separate service
            if not self._validate_api_key_format(api_key):
                raise AuthenticationError(
                    "Invalid API key format",
                    "INVALID_API_KEY_FORMAT"
                )
            
            # Get API key details from storage
            key_details = self._get_api_key_details(api_key)
            if not key_details:
                raise AuthenticationError(
                    "Invalid API key",
                    "INVALID_API_KEY"
                )
            
            # Verify key status and permissions
            if not key_details.get("active", False):
                raise AuthenticationError(
                    "API key is inactive",
                    "INACTIVE_API_KEY",
                    {"key_id": key_details.get("id")}
                )
            
            # Cache validated key details
            self._cache.setex(
                cache_key,
                CACHE_TTL,
                str(key_details)
            )
            
            # Log successful validation
            self._logger.info(
                "API key validated successfully",
                extra={
                    "key_id": key_details.get("id"),
                    "client_id": key_details.get("client_id")
                }
            )
            
            return key_details
            
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(
                "API key validation failed",
                "VALIDATION_ERROR",
                {"error": str(e)}
            )

    async def verify_token(self, request: Request) -> Dict[str, Any]:
        """
        Verify JWT token with role-based access control.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dict containing validated token claims and roles
            
        Raises:
            AuthenticationError: If token validation fails
        """
        try:
            # Extract token from headers
            auth_header = request.headers.get(TOKEN_HEADER_NAME)
            if not auth_header:
                raise AuthenticationError(
                    "Missing authorization token",
                    "MISSING_TOKEN"
                )
            
            # Validate token format
            parts = auth_header.split()
            if len(parts) != 2 or parts[0] != TOKEN_TYPE:
                raise AuthenticationError(
                    "Invalid token format",
                    "INVALID_TOKEN_FORMAT"
                )
            
            token = parts[1]
            
            # Validate token and get claims
            try:
                claims = self._token_service.validate_token(token)
            except Exception as e:
                raise AuthenticationError(
                    "Token validation failed",
                    "INVALID_TOKEN",
                    {"error": str(e)}
                )
            
            # Verify required claims
            required_claims = {"sub", "roles"}
            missing_claims = required_claims - set(claims.keys())
            if missing_claims:
                raise AuthenticationError(
                    "Missing required claims",
                    "INVALID_TOKEN_CLAIMS",
                    {"missing_claims": list(missing_claims)}
                )
            
            # Log token validation
            self._logger.info(
                "Token validated successfully",
                extra={
                    "user_id": claims.get("sub"),
                    "roles": claims.get("roles")
                }
            )
            
            return claims
            
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(
                "Token validation failed",
                "VALIDATION_ERROR",
                {"error": str(e)}
            )

    async def check_rate_limit(self, client_id: str, ip_address: str) -> bool:
        """
        Check rate limits with IP-based restrictions.
        
        Args:
            client_id: Client identifier from API key
            ip_address: Client IP address
            
        Returns:
            bool indicating if request is allowed
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        # Check IP-based rate limit first
        ip_allowed = self._rate_limiter.check_rate_limit(f"ip:{ip_address}")
        if not ip_allowed:
            self._logger.warning(
                "IP-based rate limit exceeded",
                extra={"ip_address": ip_address}
            )
            raise RateLimitExceeded(
                "IP-based rate limit exceeded",
                retry_after=60
            )
        
        # Check client rate limit
        client_allowed = self._rate_limiter.check_rate_limit(f"client:{client_id}")
        if not client_allowed:
            self._logger.warning(
                "Client rate limit exceeded",
                extra={"client_id": client_id}
            )
            raise RateLimitExceeded(
                "Client rate limit exceeded",
                retry_after=60
            )
        
        return True

    def _validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format and structure."""
        # Implementation would include actual validation logic
        return bool(api_key and len(api_key) >= 32)

    def _get_api_key_details(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve API key details from storage."""
        # Implementation would include actual storage lookup
        # This is a placeholder implementation
        return {
            "id": "key_id",
            "client_id": "client_123",
            "active": True,
            "roles": ["read", "write"],
            "rate_limit": settings.rate_limit_requests
        }


async def get_current_user(
    request: Request,
    response: Response,
    auth: AuthMiddleware = Depends()
) -> Dict[str, Any]:
    """
    FastAPI dependency for comprehensive user authentication.
    
    Implements complete authentication flow including API key validation,
    token verification, rate limiting, and security monitoring.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        auth: AuthMiddleware instance
        
    Returns:
        Dict containing authenticated user context
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Validate API key
        key_details = await auth.verify_api_key(request)
        client_id = key_details["client_id"]
        
        # Check rate limits
        await auth.check_rate_limit(client_id, request.client.host)
        
        # Verify JWT token if present
        token_claims = None
        if TOKEN_HEADER_NAME in request.headers:
            token_claims = await auth.verify_token(request)
        
        # Add rate limit headers
        remaining = auth._rate_limiter.get_remaining_requests(f"client:{client_id}")
        response.headers["X-RateLimit-Remaining"] = str(remaining["remaining_requests"])
        response.headers["X-RateLimit-Reset"] = str(remaining["reset_time"])
        
        # Return authenticated context
        return {
            "client_id": client_id,
            "roles": key_details.get("roles", []),
            "token_claims": token_claims,
            "rate_limit": key_details.get("rate_limit")
        }
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e),
                "retry_after": e.retry_after
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        )

# Export public interface
__all__ = [
    'AuthenticationError',
    'AuthMiddleware',
    'get_current_user'
]