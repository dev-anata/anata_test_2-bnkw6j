"""
FastAPI dependency injection module implementing secure service dependencies.

This module provides thread-safe dependency injection functions for service instances,
authentication, and common dependencies with comprehensive security controls and caching.

Version: 1.0.0
"""

import os
from functools import lru_cache
from typing import Dict, Any
import structlog  # version: 23.1+
from fastapi import Depends, HTTPException  # version: 0.100+
from redis import Redis  # version: 4.5+
from httpx import AsyncClient  # version: 0.24+
from circuitbreaker import circuit_breaker  # version: 1.4+

from api.auth import AuthHandler
from services.task_service import TaskService
from services.storage_service import StorageService
from core.exceptions import PipelineException
from security.token_service import TokenService
from security.key_management import KeyManager
from security.rate_limiter import RateLimiter
from config.settings import settings

# Configure structured logger
logger = structlog.get_logger(__name__)

# Environment configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', 3600))
MAX_POOL_SIZE = int(os.getenv('REDIS_POOL_SIZE', 10))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv('CIRCUIT_BREAKER_THRESHOLD', 5))

@lru_cache()
@circuit_breaker(failure_threshold=CIRCUIT_BREAKER_THRESHOLD)
def get_redis_client() -> Redis:
    """
    Get Redis client instance with connection pooling.
    
    Returns:
        Redis: Configured Redis client
        
    Raises:
        PipelineException: If Redis connection fails
    """
    try:
        return Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=MAX_POOL_SIZE
        )
    except Exception as e:
        logger.error("Failed to initialize Redis client", error=str(e))
        raise PipelineException("Redis initialization failed")

@lru_cache()
@circuit_breaker(failure_threshold=CIRCUIT_BREAKER_THRESHOLD)
def get_auth_handler() -> AuthHandler:
    """
    Get thread-safe AuthHandler instance with caching.
    
    Returns:
        AuthHandler: Cached singleton instance
        
    Raises:
        PipelineException: If initialization fails
    """
    try:
        # Initialize dependencies
        redis_client = get_redis_client()
        key_manager = KeyManager(
            project_id=settings.project_id,
            location_id=settings.region
        )
        token_service = TokenService(key_manager)
        rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_requests,
            window_size=settings.rate_limit_window
        )
        
        return AuthHandler(token_service, rate_limiter, redis_client)
        
    except Exception as e:
        logger.error("Failed to initialize AuthHandler", error=str(e))
        raise PipelineException("AuthHandler initialization failed")

@lru_cache()
@circuit_breaker(failure_threshold=CIRCUIT_BREAKER_THRESHOLD)
def get_task_service() -> TaskService:
    """
    Get thread-safe TaskService instance with health checking.
    
    Returns:
        TaskService: Cached singleton instance
        
    Raises:
        PipelineException: If initialization fails
    """
    try:
        # Initialize task service dependencies
        redis_client = get_redis_client()
        http_client = AsyncClient()
        
        # Create task service instance
        service = TaskService(
            repository=None,  # Repository will be injected by TaskService
            scheduler=None,   # Scheduler will be injected by TaskService
            executor=None     # Executor will be injected by TaskService
        )
        
        # Verify service health
        if not service.health_check():
            raise PipelineException("TaskService health check failed")
            
        return service
        
    except Exception as e:
        logger.error("Failed to initialize TaskService", error=str(e))
        raise PipelineException("TaskService initialization failed")

@lru_cache()
@circuit_breaker(failure_threshold=CIRCUIT_BREAKER_THRESHOLD)
def get_storage_service() -> StorageService:
    """
    Get thread-safe StorageService instance with connection management.
    
    Returns:
        StorageService: Cached singleton instance
        
    Raises:
        PipelineException: If initialization fails
    """
    try:
        # Initialize storage dependencies
        redis_client = get_redis_client()
        
        # Create storage service instance
        service = StorageService(
            storage_backend=None,  # Backend will be injected by StorageService
            cache_client=redis_client,
            cache_ttl_seconds=CACHE_TTL_SECONDS
        )
        
        # Verify storage connectivity
        if not service.health_check():
            raise PipelineException("StorageService health check failed")
            
        return service
        
    except Exception as e:
        logger.error("Failed to initialize StorageService", error=str(e))
        raise PipelineException("StorageService initialization failed")

async def get_current_user(
    auth_handler: AuthHandler = Depends(get_auth_handler)
) -> Dict[str, Any]:
    """
    Validate current user with comprehensive error handling.
    
    Args:
        auth_handler: Injected AuthHandler instance
        
    Returns:
        Dict containing validated user information
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Get current user with validation
        user = await auth_handler.get_current_user()
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
            
        return user
        
    except PipelineException as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Unexpected authentication error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

async def verify_admin_role(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Verify admin role with security logging.
    
    Args:
        user: Validated user information from get_current_user
        
    Returns:
        Dict containing verified admin user information
        
    Raises:
        HTTPException: If user is not an admin
    """
    try:
        # Verify admin role
        if not await auth_handler.verify_role(user, "admin"):
            logger.warning(
                "Unauthorized admin access attempt",
                user_id=user.get("id")
            )
            raise HTTPException(
                status_code=403,
                detail="Admin role required"
            )
            
        logger.info(
            "Admin access granted",
            user_id=user.get("id")
        )
        return user
        
    except PipelineException as e:
        logger.error("Role verification failed", error=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Unexpected role verification error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# Export public interface
__all__ = [
    'get_auth_handler',
    'get_task_service',
    'get_storage_service',
    'get_current_user',
    'verify_admin_role'
]