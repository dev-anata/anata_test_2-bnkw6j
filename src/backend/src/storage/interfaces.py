"""
Storage interfaces for the data processing pipeline.

This module defines abstract protocols for storage operations, providing a standardized
contract that must be implemented by different storage backends (local storage, cloud
storage, etc.). These interfaces ensure consistent data persistence behavior across
the system.

Version: 1.0.0
"""

from typing import Protocol, runtime_checkable, BinaryIO, AsyncIterator, AsyncContextManager  # version: 3.11+
from core.models import DataObject
from core.types import DataObjectID, Metadata


@runtime_checkable
@Protocol
class StorageBackend:
    """
    Protocol defining the interface for storage backend implementations.
    
    This protocol must be implemented by all storage backends (e.g., Google Cloud Storage,
    local filesystem) to provide a consistent interface for data persistence operations.
    
    The protocol supports asynchronous operations for efficient I/O handling and
    includes methods for storing, retrieving, deleting, and listing data objects.
    """

    async def store_object(self, data: BinaryIO, metadata: Metadata) -> DataObject:
        """
        Store a data object in the storage backend.
        
        Args:
            data: Binary data stream to store
            metadata: Associated metadata for the data object
            
        Returns:
            DataObject: Created data object with storage details
            
        Raises:
            StorageException: If storage operation fails
            ValidationException: If metadata is invalid
        """
        ...

    async def retrieve_object(self, object_id: DataObjectID) -> AsyncContextManager[BinaryIO]:
        """
        Retrieve a data object from storage.
        
        Args:
            object_id: Unique identifier of the data object to retrieve
            
        Returns:
            AsyncContextManager[BinaryIO]: Async context manager for accessing the data stream
            
        Raises:
            StorageException: If retrieval fails or object doesn't exist
        """
        ...

    async def delete_object(self, object_id: DataObjectID) -> bool:
        """
        Delete a data object from storage.
        
        Args:
            object_id: Unique identifier of the data object to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
            
        Raises:
            StorageException: If deletion fails
        """
        ...

    async def list_objects(self) -> AsyncIterator[DataObject]:
        """
        List all data objects in storage.
        
        Yields:
            DataObject: Data objects stored in the backend
            
        Raises:
            StorageException: If listing operation fails
        """
        ...


__all__ = ['StorageBackend']