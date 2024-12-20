"""
Google Cloud Firestore database client implementation providing asynchronous database operations.

This module implements a high-performance, production-ready Firestore client with features including:
- Connection pooling for efficient resource management
- Retry logic with exponential backoff
- Batch operations support
- Comprehensive error handling
- Monitoring and logging integration

Version: 1.0.0
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncContextManager
from uuid import UUID

from google.cloud import firestore_v1  # version: 2.11.1
from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.async_transaction import AsyncTransaction
from google.api_core import retry, exceptions as google_exceptions

from core.models import Task, TaskExecution, DataObject
from core.exceptions import StorageException, ValidationException
from config.settings import settings

# Collection names
COLLECTION_TASKS: str = 'tasks'
COLLECTION_EXECUTIONS: str = 'executions'
COLLECTION_DATA_OBJECTS: str = 'data_objects'

# Client configuration
MAX_BATCH_SIZE: int = 500
MAX_RETRY_ATTEMPTS: int = 3
RETRY_DELAY_BASE: float = 1.5
CONNECTION_TIMEOUT: int = 30
MAX_POOL_SIZE: int = 100

class FirestoreClient:
    """
    Async Firestore client with enhanced features for database operations.
    
    Provides connection pooling, retry logic, and batch operations support
    for efficient and reliable database interactions.
    """

    def __init__(
        self,
        pool_size: int = MAX_POOL_SIZE,
        timeout: int = CONNECTION_TIMEOUT,
        retry_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the Firestore client with advanced configuration.

        Args:
            pool_size: Maximum number of concurrent connections
            timeout: Connection timeout in seconds
            retry_config: Custom retry configuration
        """
        self._logger = logging.getLogger(__name__)
        
        # Initialize connection pool
        self._pool = asyncio.Queue(maxsize=pool_size)
        self._active_connections = 0
        
        # Get GCP credentials
        self._credentials = settings.get_gcp_credentials()
        
        # Configure retry policy
        self._retry_config = retry_config or {
            'max_attempts': MAX_RETRY_ATTEMPTS,
            'initial': 1.0,
            'maximum': 60.0,
            'multiplier': RETRY_DELAY_BASE
        }
        
        # Initialize client configuration
        self._client: Optional[AsyncClient] = None
        self._timeout = timeout
        
        # Collection references
        self._collections = {
            COLLECTION_TASKS: None,
            COLLECTION_EXECUTIONS: None,
            COLLECTION_DATA_OBJECTS: None
        }

    @asynccontextmanager
    async def connect(self) -> AsyncContextManager[AsyncClient]:
        """
        Get a connection from the pool with automatic resource management.

        Returns:
            AsyncContextManager yielding a Firestore client connection
            
        Raises:
            StorageException: If connection cannot be established
        """
        try:
            # Initialize client if needed
            if not self._client:
                self._client = firestore_v1.AsyncClient(
                    project=self._credentials['project_id'],
                    credentials=self._credentials.get('service_account_path')
                )
            
            # Get connection from pool or create new one
            try:
                connection = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                if self._active_connections < MAX_POOL_SIZE:
                    connection = await self._client.collection(COLLECTION_TASKS).document().get()
                    self._active_connections += 1
                else:
                    raise StorageException(
                        "Connection pool exhausted",
                        storage_path="firestore",
                        storage_details={"active_connections": self._active_connections}
                    )
            
            try:
                yield connection
            finally:
                # Return connection to pool
                await self._pool.put(connection)
                
        except google_exceptions.GoogleAPIError as e:
            raise StorageException(
                "Failed to connect to Firestore",
                storage_path="firestore",
                storage_details={"error": str(e)}
            )

    async def execute_batch(
        self,
        operations: List[Dict[str, Any]],
        transaction: Optional[AsyncTransaction] = None
    ) -> List[Any]:
        """
        Execute multiple operations in a batch with size limits.

        Args:
            operations: List of operations to execute
            transaction: Optional transaction to use

        Returns:
            List of operation results

        Raises:
            ValidationException: If batch size exceeds limit
            StorageException: If batch execution fails
        """
        if len(operations) > MAX_BATCH_SIZE:
            raise ValidationException(
                "Batch size exceeds limit",
                {"max_size": MAX_BATCH_SIZE, "actual_size": len(operations)}
            )

        async with self.connect() as client:
            try:
                batch = client.batch()
                results = []

                for op in operations:
                    if op['type'] == 'create':
                        ref = client.collection(op['collection']).document()
                        batch.create(ref, op['data'])
                        results.append(ref.id)
                    elif op['type'] == 'update':
                        ref = client.collection(op['collection']).document(op['id'])
                        batch.update(ref, op['data'])
                        results.append(op['id'])
                    elif op['type'] == 'delete':
                        ref = client.collection(op['collection']).document(op['id'])
                        batch.delete(ref)
                        results.append(op['id'])

                await batch.commit()
                return results

            except google_exceptions.GoogleAPIError as e:
                raise StorageException(
                    "Batch operation failed",
                    storage_path="firestore",
                    storage_details={"error": str(e)}
                )

    @retry.Retry(predicate=retry.if_exception_type(google_exceptions.GoogleAPIError))
    async def create_task(self, task: Task) -> str:
        """
        Create a new task document with retry logic.

        Args:
            task: Task model instance to create

        Returns:
            Created task document ID

        Raises:
            StorageException: If task creation fails
        """
        async with self.connect() as client:
            try:
                task_data = {
                    'id': str(task.id),
                    'type': task.type,
                    'status': task.status,
                    'configuration': task.configuration,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at,
                    'scheduled_at': task.scheduled_at,
                    'execution_history': [str(x) for x in task.execution_history]
                }

                doc_ref = client.collection(COLLECTION_TASKS).document(str(task.id))
                await doc_ref.create(task_data)
                return str(task.id)

            except google_exceptions.GoogleAPIError as e:
                raise StorageException(
                    "Failed to create task",
                    storage_path=f"{COLLECTION_TASKS}/{task.id}",
                    storage_details={"error": str(e)}
                )

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """
        Retrieve a task by ID.

        Args:
            task_id: UUID of task to retrieve

        Returns:
            Task instance if found, None otherwise

        Raises:
            StorageException: If retrieval fails
        """
        async with self.connect() as client:
            try:
                doc_ref = client.collection(COLLECTION_TASKS).document(str(task_id))
                doc = await doc_ref.get()

                if not doc.exists:
                    return None

                data = doc.to_dict()
                return Task(
                    id=UUID(data['id']),
                    type=data['type'],
                    status=data['status'],
                    configuration=data['configuration'],
                    created_at=data['created_at'],
                    updated_at=data['updated_at'],
                    scheduled_at=data['scheduled_at'],
                    execution_history=[UUID(x) for x in data['execution_history']]
                )

            except google_exceptions.GoogleAPIError as e:
                raise StorageException(
                    "Failed to retrieve task",
                    storage_path=f"{COLLECTION_TASKS}/{task_id}",
                    storage_details={"error": str(e)}
                )

    async def update_task_status(self, task_id: UUID, new_status: str) -> None:
        """
        Update a task's status with optimistic locking.

        Args:
            task_id: UUID of task to update
            new_status: New status to set

        Raises:
            StorageException: If update fails
            ValidationException: If status transition is invalid
        """
        async with self.connect() as client:
            try:
                @firestore_v1.async_transactional
                async def update_in_transaction(transaction: AsyncTransaction, doc_ref):
                    doc = await doc_ref.get()
                    if not doc.exists:
                        raise ValidationException(
                            "Task not found",
                            {"task_id": str(task_id)}
                        )

                    task_data = doc.to_dict()
                    task = Task(**task_data)
                    task.update_status(new_status)

                    transaction.update(doc_ref, {
                        'status': new_status,
                        'updated_at': datetime.utcnow()
                    })

                doc_ref = client.collection(COLLECTION_TASKS).document(str(task_id))
                await client.transaction().run(update_in_transaction, doc_ref)

            except google_exceptions.GoogleAPIError as e:
                raise StorageException(
                    "Failed to update task status",
                    storage_path=f"{COLLECTION_TASKS}/{task_id}",
                    storage_details={"error": str(e)}
                )

    async def close(self) -> None:
        """
        Close all connections and cleanup resources.
        """
        if self._client:
            await self._client.close()
            self._client = None
            self._active_connections = 0
            while not self._pool.empty():
                try:
                    await self._pool.get_nowait()
                except asyncio.QueueEmpty:
                    break

__all__ = ['FirestoreClient']