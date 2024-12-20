"""
Local filesystem storage backend implementation.

This module provides a local filesystem-based implementation of the StorageBackend
protocol for development and testing purposes. It supports async I/O operations
and maintains metadata alongside stored objects.

Version: 1.0.0
"""

import os
from os import path
import json
from uuid import uuid4  # version: 3.11+
import aiofiles  # version: 23.1+
from typing import AsyncIterator, AsyncContextManager, BinaryIO, Dict, Any  # version: 3.11+

from storage.interfaces import StorageBackend
from core.models import DataObject
from core.types import DataObjectID, Metadata
from core.exceptions import StorageException

# Default storage location if not specified
DEFAULT_STORAGE_PATH = os.getenv('LOCAL_STORAGE_PATH', '/tmp/pipeline_storage')

class LocalStorageBackend(StorageBackend):
    """
    Local filesystem implementation of StorageBackend protocol.
    
    Provides a development and testing-friendly storage backend that implements
    the full StorageBackend protocol with async I/O operations and metadata
    management.
    
    Attributes:
        _storage_path (str): Base path for stored files
    """
    
    def __init__(self, storage_path: str = DEFAULT_STORAGE_PATH) -> None:
        """
        Initialize local storage backend.
        
        Args:
            storage_path: Base directory for stored files
            
        Raises:
            StorageException: If storage path is invalid or inaccessible
        """
        self._storage_path = path.abspath(storage_path)
        
        try:
            # Create storage directory if it doesn't exist
            if not path.exists(self._storage_path):
                os.makedirs(self._storage_path)
            
            # Verify write permissions
            test_file = path.join(self._storage_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
                
        except (OSError, IOError) as e:
            raise StorageException(
                f"Failed to initialize storage at {storage_path}",
                storage_path,
                {"error": str(e)}
            )

    def _get_object_path(self, object_id: DataObjectID) -> str:
        """
        Get filesystem path for a data object.
        
        Args:
            object_id: Unique identifier of the data object
            
        Returns:
            str: Absolute filesystem path for the object
        """
        return path.join(self._storage_path, str(object_id))

    def _get_metadata_path(self, object_id: DataObjectID) -> str:
        """
        Get filesystem path for object metadata.
        
        Args:
            object_id: Unique identifier of the data object
            
        Returns:
            str: Absolute filesystem path for metadata file
        """
        return f"{self._get_object_path(object_id)}.meta"

    async def store_object(self, data: BinaryIO, metadata: Metadata) -> DataObject:
        """
        Store a data object in the local filesystem.
        
        Args:
            data: Binary data to store
            metadata: Associated metadata
            
        Returns:
            DataObject: Created data object with storage details
            
        Raises:
            StorageException: If storage operation fails
        """
        object_id = uuid4()
        object_path = self._get_object_path(object_id)
        metadata_path = self._get_metadata_path(object_id)
        
        try:
            # Store binary data
            async with aiofiles.open(object_path, 'wb') as f:
                while chunk := data.read(8192):  # 8KB chunks
                    await f.write(chunk)
            
            # Store metadata
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata))
            
            return DataObject(
                id=object_id,
                execution_id=metadata.get('execution_id'),
                storage_path=object_path,
                content_type=metadata.get('content_type', 'application/octet-stream'),
                metadata=metadata
            )
            
        except (OSError, IOError) as e:
            # Clean up any partially written files
            for file_path in [object_path, metadata_path]:
                if path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                        
            raise StorageException(
                "Failed to store object",
                object_path,
                {"error": str(e)}
            )

    async def retrieve_object(self, object_id: DataObjectID) -> AsyncContextManager[BinaryIO]:
        """
        Retrieve a data object from local storage.
        
        Args:
            object_id: Unique identifier of the data object
            
        Returns:
            AsyncContextManager[BinaryIO]: Async context manager for file access
            
        Raises:
            StorageException: If object doesn't exist or is inaccessible
        """
        object_path = self._get_object_path(object_id)
        
        if not path.exists(object_path):
            raise StorageException(
                f"Object {object_id} not found",
                object_path,
                {"error": "file_not_found"}
            )
            
        try:
            return aiofiles.open(object_path, 'rb')
        except (OSError, IOError) as e:
            raise StorageException(
                f"Failed to retrieve object {object_id}",
                object_path,
                {"error": str(e)}
            )

    async def delete_object(self, object_id: DataObjectID) -> bool:
        """
        Delete a data object and its metadata.
        
        Args:
            object_id: Unique identifier of the data object
            
        Returns:
            bool: True if deletion was successful
            
        Raises:
            StorageException: If deletion fails
        """
        object_path = self._get_object_path(object_id)
        metadata_path = self._get_metadata_path(object_id)
        success = True
        
        for file_path in [object_path, metadata_path]:
            if path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    success = False
                    raise StorageException(
                        f"Failed to delete {path.basename(file_path)}",
                        file_path,
                        {"error": str(e)}
                    )
                    
        return success

    async def list_objects(self) -> AsyncIterator[DataObject]:
        """
        List all data objects in storage.
        
        Yields:
            DataObject: Data objects stored in the backend
            
        Raises:
            StorageException: If listing operation fails
        """
        try:
            for filename in os.listdir(self._storage_path):
                # Skip metadata files and any temporary files
                if filename.endswith('.meta') or filename.startswith('.'):
                    continue
                    
                object_id = filename  # Filename is the object ID
                metadata_path = self._get_metadata_path(object_id)
                
                # Load metadata if it exists
                try:
                    async with aiofiles.open(metadata_path, 'r') as f:
                        metadata = json.loads(await f.read())
                        
                    yield DataObject(
                        id=object_id,
                        execution_id=metadata.get('execution_id'),
                        storage_path=self._get_object_path(object_id),
                        content_type=metadata.get('content_type', 'application/octet-stream'),
                        metadata=metadata
                    )
                except (OSError, IOError, json.JSONDecodeError) as e:
                    # Log warning but continue listing other objects
                    print(f"Warning: Failed to load metadata for {object_id}: {e}")
                    continue
                    
        except OSError as e:
            raise StorageException(
                "Failed to list objects",
                self._storage_path,
                {"error": str(e)}
            )

__all__ = ['LocalStorageBackend']