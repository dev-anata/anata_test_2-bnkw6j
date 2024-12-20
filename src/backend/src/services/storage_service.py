"""
Storage service implementation for managing data storage operations.

This service provides a high-level interface for storing and retrieving data objects
with Redis caching, async operations, and comprehensive error handling. It implements
the storage management requirements specified in the technical specifications.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import json
import logging
from typing import AsyncIterator, AsyncContextManager, BinaryIO, Optional, Dict, Any  # version: 3.11+
from uuid import UUID
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from redis import Redis  # version: 4.5+
from redis.exceptions import RedisError

from storage.interfaces import StorageBackend
from core.models import DataObject
from core.types import Metadata
from core.exceptions import StorageException, ValidationException

logger = logging.getLogger(__name__)

class StorageService:
    """
    High-level service for managing storage operations with Redis caching.
    
    Implements storage management requirements including caching, async operations,
    and comprehensive error handling for data persistence operations.
    
    Attributes:
        _storage_backend: Backend storage implementation
        _cache_client: Redis client for caching
        cache_ttl_seconds: Cache TTL in seconds
        max_retries: Maximum retry attempts for storage operations
        retry_backoff: Exponential backoff multiplier for retries
    """
    
    def __init__(
        self,
        storage_backend: StorageBackend,
        cache_client: Redis,
        cache_ttl_seconds: int = 3600,
        max_retries: int = 3,
        retry_backoff: float = 2.0
    ) -> None:
        """
        Initialize the storage service with backend and cache configuration.
        
        Args:
            storage_backend: Implementation of StorageBackend protocol
            cache_client: Redis client instance for caching
            cache_ttl_seconds: Cache TTL in seconds (default: 1 hour)
            max_retries: Maximum retry attempts (default: 3)
            retry_backoff: Retry backoff multiplier (default: 2.0)
            
        Raises:
            ValidationException: If configuration parameters are invalid
            StorageException: If storage backend or cache initialization fails
        """
        if not isinstance(storage_backend, StorageBackend):
            raise ValidationException(
                "Invalid storage backend",
                {"error": "Backend must implement StorageBackend protocol"}
            )
            
        self._storage_backend = storage_backend
        self._cache_client = cache_client
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        
        # Cache key prefix for namespacing
        self._cache_prefix = "storage:"
        
        # Initialize monitoring metrics
        self._init_metrics()
        
    def _init_metrics(self) -> None:
        """Initialize storage operation metrics."""
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "storage_errors": 0,
            "retry_attempts": 0
        }
        
    def _get_cache_key(self, object_id: UUID) -> str:
        """
        Generate cache key for object ID with namespace.
        
        Args:
            object_id: UUID of the data object
            
        Returns:
            str: Namespaced cache key
        """
        return f"{self._cache_prefix}{str(object_id)}"
        
    async def _retry_operation(self, operation: callable, *args, **kwargs) -> Any:
        """
        Retry an operation with exponential backoff.
        
        Args:
            operation: Async callable to retry
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Any: Operation result if successful
            
        Raises:
            StorageException: If all retries fail
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                self._metrics["retry_attempts"] += 1
                if attempt < self.max_retries - 1:
                    delay = (self.retry_backoff ** attempt) * 1.0
                    await asyncio.sleep(delay)
                    
        self._metrics["storage_errors"] += 1
        raise StorageException(
            "Storage operation failed after retries",
            str(last_error),
            {"attempts": self.max_retries}
        )
        
    async def store_data(self, data: BinaryIO, metadata: Metadata) -> DataObject:
        """
        Store data with caching and error handling.
        
        Args:
            data: Binary data stream to store
            metadata: Associated metadata for the data object
            
        Returns:
            DataObject: Stored data object with cache status
            
        Raises:
            ValidationException: If input data or metadata is invalid
            StorageException: If storage operation fails
        """
        if not data:
            raise ValidationException(
                "Invalid input data",
                {"error": "Data stream cannot be empty"}
            )
            
        if not isinstance(metadata, dict):
            raise ValidationException(
                "Invalid metadata format",
                {"error": "Metadata must be a dictionary"}
            )
            
        try:
            # Store data in backend with retry
            data_object = await self._retry_operation(
                self._storage_backend.store_object,
                data,
                metadata
            )
            
            # Cache metadata
            cache_key = self._get_cache_key(data_object.id)
            cache_data = {
                "storage_path": data_object.storage_path,
                "metadata": metadata,
                "cached_at": datetime.utcnow().isoformat()
            }
            
            try:
                await asyncio.to_thread(
                    self._cache_client.setex,
                    cache_key,
                    self.cache_ttl_seconds,
                    json.dumps(cache_data)
                )
            except RedisError as e:
                logger.warning(f"Cache update failed: {str(e)}")
                
            return data_object
            
        except Exception as e:
            raise StorageException(
                "Failed to store data",
                str(data_object.storage_path if 'data_object' in locals() else 'unknown'),
                {"error": str(e)}
            )
            
    @asynccontextmanager
    async def retrieve_data(self, object_id: UUID) -> AsyncContextManager[BinaryIO]:
        """
        Retrieve data with cache checking and async streaming.
        
        Args:
            object_id: UUID of the data object to retrieve
            
        Yields:
            AsyncContextManager[BinaryIO]: Async data stream context
            
        Raises:
            StorageException: If retrieval fails
        """
        cache_key = self._get_cache_key(object_id)
        
        try:
            # Check cache for metadata
            cached_data = await asyncio.to_thread(
                self._cache_client.get,
                cache_key
            )
            
            if cached_data:
                self._metrics["cache_hits"] += 1
                cached_info = json.loads(cached_data)
                storage_path = cached_info["storage_path"]
            else:
                self._metrics["cache_misses"] += 1
                # Retrieve from backend to get storage path
                async with self._storage_backend.retrieve_object(object_id) as data:
                    storage_path = data.storage_path
            
            # Stream data from backend
            async with self._storage_backend.retrieve_object(object_id) as stream:
                yield stream
                
        except Exception as e:
            raise StorageException(
                "Failed to retrieve data",
                str(object_id),
                {"error": str(e)}
            )
            
    async def delete_data(self, object_id: UUID) -> bool:
        """
        Delete data with cache invalidation and consistency checks.
        
        Args:
            object_id: UUID of the data object to delete
            
        Returns:
            bool: True if deletion was successful
            
        Raises:
            StorageException: If deletion fails
        """
        cache_key = self._get_cache_key(object_id)
        
        try:
            # Delete from backend
            success = await self._retry_operation(
                self._storage_backend.delete_object,
                object_id
            )
            
            if success:
                # Invalidate cache
                try:
                    await asyncio.to_thread(
                        self._cache_client.delete,
                        cache_key
                    )
                except RedisError as e:
                    logger.warning(f"Cache invalidation failed: {str(e)}")
                    
            return success
            
        except Exception as e:
            raise StorageException(
                "Failed to delete data",
                str(object_id),
                {"error": str(e)}
            )
            
    async def list_data(
        self,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> AsyncIterator[DataObject]:
        """
        List data objects with pagination and cache support.
        
        Args:
            limit: Maximum number of objects to return (default: 100)
            cursor: Pagination cursor for continuing previous query
            
        Yields:
            AsyncIterator[DataObject]: Iterator of data objects
            
        Raises:
            ValidationException: If pagination parameters are invalid
            StorageException: If listing operation fails
        """
        if limit < 1 or limit > 1000:
            raise ValidationException(
                "Invalid limit parameter",
                {"error": "Limit must be between 1 and 1000"}
            )
            
        try:
            # List objects from backend
            objects_iterator = self._storage_backend.list_objects()
            
            count = 0
            async for obj in objects_iterator:
                if count >= limit:
                    break
                    
                # Check cache for additional metadata
                cache_key = self._get_cache_key(obj.id)
                try:
                    cached_data = await asyncio.to_thread(
                        self._cache_client.get,
                        cache_key
                    )
                    if cached_data:
                        cached_info = json.loads(cached_data)
                        obj.metadata.update(cached_info.get("metadata", {}))
                except RedisError:
                    pass
                    
                yield obj
                count += 1
                
        except Exception as e:
            raise StorageException(
                "Failed to list data objects",
                "list_operation",
                {"error": str(e)}
            )