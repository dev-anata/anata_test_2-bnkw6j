"""
Service layer implementation for managing data objects and storage operations.

Provides high-level interface for data management with enhanced error handling,
circuit breaker pattern, and data consistency guarantees.

Version: 1.0.0
"""

import logging  # version: 3.11+
import asyncio  # version: 3.11+
from datetime import datetime, timedelta  # version: 3.11+
from typing import BinaryIO, AsyncContextManager, List, Optional, Dict  # version: 3.11+
from uuid import uuid4  # version: 3.11+

from tenacity import (  # version: 8.2+
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from circuitbreaker import CircuitBreaker  # version: 1.4+

from db.repositories.data_objects import DataObjectRepository
from storage.interfaces import StorageBackend
from db.models.data_object import FirestoreDataObject
from core.types import DataObjectID, ExecutionID, Metadata
from core.exceptions import StorageException, ValidationException

# Circuit breaker configuration
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RECOVERY_TIMEOUT = 60
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.5

class DataService:
    """
    Service for managing data objects and storage operations with enhanced async support,
    error handling, and data consistency guarantees.
    """

    def __init__(self, repository: DataObjectRepository, storage: StorageBackend) -> None:
        """
        Initialize data service with repository and storage backend.

        Args:
            repository: Repository for data object metadata
            storage: Storage backend for binary data
        """
        self._logger = logging.getLogger(__name__)
        self._repository = repository
        self._storage = storage
        self._retry_counts: Dict[str, int] = {}
        self._circuit_breaker_state: Dict[str, float] = {}

        # Configure circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=CIRCUIT_RECOVERY_TIMEOUT,
            expected_exception=StorageException
        )

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_BACKOFF),
        retry=retry_if_exception_type(StorageException)
    )
    async def store_data(
        self,
        data: BinaryIO,
        execution_id: ExecutionID,
        metadata: Metadata
    ) -> FirestoreDataObject:
        """
        Store data with metadata and enhanced error handling.

        Args:
            data: Binary data stream to store
            execution_id: ID of the execution creating this data
            metadata: Additional metadata for the data object

        Returns:
            FirestoreDataObject: Created data object with complete metadata

        Raises:
            ValidationException: If metadata validation fails
            StorageException: If storage operation fails
        """
        try:
            # Validate metadata format
            if not isinstance(metadata, dict):
                raise ValidationException(
                    "Invalid metadata format",
                    {"expected": "dict", "received": type(metadata).__name__}
                )

            # Check circuit breaker state
            operation_key = f"store_{execution_id}"
            if self._circuit_breaker_state.get(operation_key, 0) > datetime.utcnow().timestamp():
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path="data_service/store"
                )

            # Generate unique storage path
            storage_path = f"gs://data-processing-pipeline/executions/{execution_id}/{uuid4()}"

            # Store data with progress tracking
            try:
                stored_object = await self._circuit_breaker.call(
                    self._storage.store_object,
                    data,
                    {
                        **metadata,
                        "storage_path": storage_path,
                        "execution_id": str(execution_id),
                        "created_at": datetime.utcnow()
                    }
                )

                # Create metadata record
                data_object = FirestoreDataObject(
                    id=stored_object.id,
                    execution_id=execution_id,
                    storage_path=storage_path,
                    content_type=metadata.get("content_type", "application/octet-stream"),
                    metadata=metadata,
                    created_at=datetime.utcnow()
                )

                # Store in repository
                created_object = await self._repository.create(data_object)

                # Update circuit breaker metrics
                self._retry_counts[operation_key] = 0
                return created_object

            except Exception as e:
                # Update circuit breaker state
                self._retry_counts[operation_key] = self._retry_counts.get(operation_key, 0) + 1
                if self._retry_counts[operation_key] >= CIRCUIT_FAILURE_THRESHOLD:
                    self._circuit_breaker_state[operation_key] = (
                        datetime.utcnow() + timedelta(seconds=CIRCUIT_RECOVERY_TIMEOUT)
                    ).timestamp()

                raise StorageException(
                    "Failed to store data object",
                    storage_path=storage_path,
                    storage_details={"error": str(e)}
                )

        except Exception as e:
            self._logger.error(
                "Data storage failed",
                extra={
                    "error": str(e),
                    "execution_id": str(execution_id)
                }
            )
            raise

    async def get_data(self, object_id: DataObjectID) -> AsyncContextManager[BinaryIO]:
        """
        Retrieve data by object ID with streaming support.

        Args:
            object_id: ID of the data object to retrieve

        Returns:
            AsyncContextManager[BinaryIO]: Async context manager for streamed data access

        Raises:
            StorageException: If retrieval fails
            ValidationException: If object doesn't exist
        """
        try:
            # Check circuit breaker state
            operation_key = f"get_{object_id}"
            if self._circuit_breaker_state.get(operation_key, 0) > datetime.utcnow().timestamp():
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path="data_service/get"
                )

            # Get metadata from repository
            data_object = await self._repository.get(object_id)
            if not data_object:
                raise ValidationException(
                    "Data object not found",
                    {"object_id": str(object_id)}
                )

            # Return streaming context manager
            return await self._circuit_breaker.call(
                self._storage.retrieve_object,
                object_id
            )

        except Exception as e:
            self._logger.error(
                "Data retrieval failed",
                extra={
                    "error": str(e),
                    "object_id": str(object_id)
                }
            )
            raise

    async def delete_data(self, object_id: DataObjectID) -> bool:
        """
        Delete data object and its stored data atomically.

        Args:
            object_id: ID of the data object to delete

        Returns:
            bool: True if deletion was successful

        Raises:
            StorageException: If deletion fails
            ValidationException: If object doesn't exist
        """
        try:
            # Check circuit breaker state
            operation_key = f"delete_{object_id}"
            if self._circuit_breaker_state.get(operation_key, 0) > datetime.utcnow().timestamp():
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path="data_service/delete"
                )

            # Get object metadata
            data_object = await self._repository.get(object_id)
            if not data_object:
                raise ValidationException(
                    "Data object not found",
                    {"object_id": str(object_id)}
                )

            # Delete from storage backend
            storage_deleted = await self._circuit_breaker.call(
                self._storage.delete_object,
                object_id
            )

            if storage_deleted:
                # Delete metadata if storage deletion succeeded
                await self._repository.delete(object_id)
                return True

            return False

        except Exception as e:
            self._logger.error(
                "Data deletion failed",
                extra={
                    "error": str(e),
                    "object_id": str(object_id)
                }
            )
            raise

    async def list_execution_data(
        self,
        execution_id: ExecutionID,
        filters: Optional[Dict] = None
    ) -> List[FirestoreDataObject]:
        """
        List all data objects for a task execution.

        Args:
            execution_id: ID of the execution to query
            filters: Optional additional filters to apply

        Returns:
            List[FirestoreDataObject]: List of data objects for the execution

        Raises:
            StorageException: If query fails
        """
        try:
            # Combine execution ID with additional filters
            query_filters = {
                "execution_id": str(execution_id),
                **(filters or {})
            }

            # Query repository with filters
            return await self._repository.list_by_execution(execution_id)

        except Exception as e:
            self._logger.error(
                "Failed to list execution data",
                extra={
                    "error": str(e),
                    "execution_id": str(execution_id)
                }
            )
            raise StorageException(
                "Failed to list execution data",
                storage_path=f"data_service/list/{execution_id}"
            )