"""
Integration tests for storage backends (local and cloud storage).

This module provides comprehensive integration tests for storage backends,
verifying data persistence operations, performance requirements, and protocol
compliance with extensive error handling and concurrent operation testing.

Version: 1.0.0
"""

import asyncio
import hashlib
import os
import tempfile
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional
from uuid import uuid4

import pytest  # version: 7.4+
import pytest_asyncio  # version: 0.21+
import aiofiles  # version: 23.1+

from storage.interfaces import StorageBackend
from storage.local import LocalStorageBackend
from storage.cloud_storage import CloudStorageBackend
from core.models import DataObject
from core.exceptions import StorageException
from tests.utils.fixtures import create_test_data_object

# Test configuration
TEST_DATA_SIZE = 1024 * 1024 * 100  # 100MB for performance testing
PERFORMANCE_THRESHOLD_MBS = 50  # 50MB/s minimum throughput
CONCURRENT_OPERATIONS = 10  # Number of concurrent operations for testing

TEST_METADATA = {
    "content_type": "application/octet-stream",
    "source": "integration-test",
    "attributes": {
        "test_type": "storage_integration",
        "version": "1.0"
    }
}

@pytest.fixture(params=["local", "cloud"])
async def storage_backend(request) -> AsyncIterator[StorageBackend]:
    """
    Fixture providing configured storage backend instances for testing.
    
    Args:
        request: Pytest request object containing backend type parameter
        
    Yields:
        StorageBackend: Configured storage backend instance
    """
    if request.param == "local":
        # Set up local storage backend with temporary directory
        temp_dir = tempfile.mkdtemp(prefix="storage_test_")
        backend = LocalStorageBackend(storage_path=temp_dir)
        yield backend
        # Cleanup temporary directory after tests
        try:
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(temp_dir)
        except OSError as e:
            pytest.fail(f"Failed to cleanup test directory: {e}")
            
    else:
        # Set up cloud storage backend with test bucket
        test_bucket = f"test-bucket-{uuid4()}"
        backend = CloudStorageBackend(
            bucket_name=test_bucket,
            region="us-central1",
            enable_versioning=True
        )
        yield backend
        # Cleanup test bucket after tests
        try:
            await backend.delete_bucket(force=True)
        except StorageException as e:
            pytest.fail(f"Failed to cleanup test bucket: {e}")

@pytest.mark.asyncio
async def test_basic_storage_operations(storage_backend: StorageBackend):
    """
    Test basic storage operations with data integrity verification.
    
    Verifies store, retrieve, delete and list operations work correctly
    and maintain data integrity.
    """
    # Generate test data with known hash
    test_data = os.urandom(1024 * 1024)  # 1MB test data
    test_hash = hashlib.sha256(test_data).hexdigest()
    
    # Test store operation
    async with aiofiles.tempfile.NamedTemporaryFile() as temp_file:
        await temp_file.write(test_data)
        await temp_file.seek(0)
        
        stored_object = await storage_backend.store_object(
            temp_file,
            TEST_METADATA
        )
        
        assert isinstance(stored_object, DataObject)
        assert stored_object.content_type == TEST_METADATA["content_type"]
        assert stored_object.metadata == TEST_METADATA
    
    # Test retrieve operation and verify data integrity
    async with await storage_backend.retrieve_object(stored_object.id) as retrieved_file:
        retrieved_data = await retrieved_file.read()
        retrieved_hash = hashlib.sha256(retrieved_data).hexdigest()
        
        assert retrieved_hash == test_hash
        
    # Test list operation
    objects_found = False
    async for obj in storage_backend.list_objects():
        if obj.id == stored_object.id:
            objects_found = True
            assert obj.content_type == TEST_METADATA["content_type"]
            assert obj.metadata == TEST_METADATA
            break
    assert objects_found
    
    # Test delete operation
    assert await storage_backend.delete_object(stored_object.id)
    
    # Verify object no longer exists
    with pytest.raises(StorageException):
        async with await storage_backend.retrieve_object(stored_object.id):
            pass

@pytest.mark.asyncio
@pytest.mark.performance
async def test_storage_performance(storage_backend: StorageBackend):
    """
    Test storage I/O performance with large datasets.
    
    Verifies storage backend meets minimum throughput requirements
    of 50MB/s for both upload and download operations.
    """
    # Generate large test dataset
    test_data = os.urandom(TEST_DATA_SIZE)
    
    # Test upload performance
    start_time = datetime.utcnow()
    async with aiofiles.tempfile.NamedTemporaryFile() as temp_file:
        await temp_file.write(test_data)
        await temp_file.seek(0)
        
        stored_object = await storage_backend.store_object(
            temp_file,
            TEST_METADATA
        )
    
    upload_time = (datetime.utcnow() - start_time).total_seconds()
    upload_speed_mbs = TEST_DATA_SIZE / (1024 * 1024 * upload_time)
    
    assert upload_speed_mbs >= PERFORMANCE_THRESHOLD_MBS, \
        f"Upload speed {upload_speed_mbs:.2f}MB/s below threshold {PERFORMANCE_THRESHOLD_MBS}MB/s"
    
    # Test download performance
    start_time = datetime.utcnow()
    async with await storage_backend.retrieve_object(stored_object.id) as retrieved_file:
        await retrieved_file.read()
    
    download_time = (datetime.utcnow() - start_time).total_seconds()
    download_speed_mbs = TEST_DATA_SIZE / (1024 * 1024 * download_time)
    
    assert download_speed_mbs >= PERFORMANCE_THRESHOLD_MBS, \
        f"Download speed {download_speed_mbs:.2f}MB/s below threshold {PERFORMANCE_THRESHOLD_MBS}MB/s"

@pytest.mark.asyncio
async def test_concurrent_operations(storage_backend: StorageBackend):
    """
    Test concurrent storage operations and race conditions.
    
    Verifies storage backend handles multiple simultaneous operations
    correctly without data corruption or race conditions.
    """
    # Generate test data objects
    test_objects = []
    for _ in range(CONCURRENT_OPERATIONS):
        test_data = os.urandom(1024 * 1024)  # 1MB per object
        async with aiofiles.tempfile.NamedTemporaryFile() as temp_file:
            await temp_file.write(test_data)
            await temp_file.seek(0)
            test_objects.append((temp_file.name, test_data))
    
    # Test concurrent uploads
    async def upload_object(file_path: str) -> DataObject:
        async with aiofiles.open(file_path, 'rb') as f:
            return await storage_backend.store_object(f, TEST_METADATA)
    
    upload_tasks = [
        upload_object(obj[0]) for obj in test_objects
    ]
    stored_objects = await asyncio.gather(*upload_tasks)
    
    assert len(stored_objects) == CONCURRENT_OPERATIONS
    
    # Test concurrent downloads
    async def verify_object(obj_id: str, expected_data: bytes) -> bool:
        async with await storage_backend.retrieve_object(obj_id) as f:
            data = await f.read()
            return hashlib.sha256(data).hexdigest() == hashlib.sha256(expected_data).hexdigest()
    
    verify_tasks = [
        verify_object(obj.id, test_objects[i][1])
        for i, obj in enumerate(stored_objects)
    ]
    verification_results = await asyncio.gather(*verify_tasks)
    
    assert all(verification_results)
    
    # Test concurrent deletions
    delete_tasks = [
        storage_backend.delete_object(obj.id)
        for obj in stored_objects
    ]
    deletion_results = await asyncio.gather(*delete_tasks)
    
    assert all(deletion_results)

@pytest.mark.asyncio
async def test_error_handling(storage_backend: StorageBackend):
    """
    Test storage error scenarios and recovery.
    
    Verifies storage backend handles error conditions gracefully
    and provides appropriate error information.
    """
    # Test invalid object retrieval
    with pytest.raises(StorageException) as exc_info:
        async with await storage_backend.retrieve_object(uuid4()):
            pass
    assert "not found" in str(exc_info.value).lower()
    
    # Test invalid data storage
    with pytest.raises(StorageException):
        await storage_backend.store_object(None, TEST_METADATA)
    
    # Test metadata validation
    with pytest.raises(StorageException):
        async with aiofiles.tempfile.NamedTemporaryFile() as temp_file:
            await temp_file.write(b"test")
            await temp_file.seek(0)
            await storage_backend.store_object(temp_file, {"invalid": None})
    
    # Test concurrent modification
    test_data = b"test data"
    async with aiofiles.tempfile.NamedTemporaryFile() as temp_file:
        await temp_file.write(test_data)
        await temp_file.seek(0)
        
        obj = await storage_backend.store_object(temp_file, TEST_METADATA)
        
        # Attempt concurrent modifications
        tasks = [
            storage_backend.delete_object(obj.id),
            storage_backend.delete_object(obj.id)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify only one operation succeeded
        assert any(isinstance(r, StorageException) for r in results)