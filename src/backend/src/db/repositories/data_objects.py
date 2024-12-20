"""
Repository implementation for managing data objects in Cloud Firestore.

Provides CRUD operations and queries for processed data outputs from scraping and OCR tasks
with enhanced error handling, data validation, and time-based partitioning.

Version: 1.0.0
"""

from datetime import datetime, timedelta  # version: 3.11+
from typing import Dict, List, Optional, Tuple, Any  # version: 3.11+
from uuid import UUID  # version: 3.11+
import logging  # version: 3.11+

from google.cloud.firestore_v1.base_query import FieldFilter  # version: 2.11.1
from tenacity import (  # version: 8.2+
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from db.repositories.base import BaseRepository
from db.models.data_object import FirestoreDataObject
from core.types import DataObjectID, ExecutionID, Metadata
from core.exceptions import StorageException, ValidationException

class DataObjectRepository(BaseRepository[FirestoreDataObject]):
    """
    Repository implementation for managing data objects in Cloud Firestore with enhanced
    error handling and data validation.
    
    Implements time-based partitioning, optimized queries, and comprehensive error handling
    for data object storage operations.
    """

    def __init__(self, retry_attempts: int = 3, backoff_factor: float = 1.5) -> None:
        """
        Initialize data object repository with error handling configuration.
        
        Args:
            retry_attempts: Maximum number of retry attempts for failed operations
            backoff_factor: Exponential backoff multiplier between retries
        """
        super().__init__('data_objects')
        self._logger = logging.getLogger(__name__)
        self._retry_attempts = retry_attempts
        self._backoff_factor = backoff_factor
        self._circuit_open = False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5),
        retry=retry_if_exception_type(StorageException)
    )
    async def create(self, data_object: FirestoreDataObject) -> FirestoreDataObject:
        """
        Create a new data object in Firestore with validation and error handling.
        
        Args:
            data_object: FirestoreDataObject instance to create
            
        Returns:
            Created data object with assigned ID
            
        Raises:
            ValidationException: If data object validation fails
            StorageException: If creation operation fails
        """
        try:
            # Validate input data object
            if not await self.validate_entity(data_object):
                raise ValidationException(
                    "Data object validation failed",
                    {"object_id": str(data_object.id)}
                )

            # Convert to Firestore dictionary
            data_dict = data_object.to_dict()
            
            # Add partition key for time-based partitioning
            partition_key = data_object.created_at.strftime("%Y%m")
            data_dict['partition_key'] = partition_key

            # Create document with circuit breaker protection
            if not self._circuit_open:
                doc_ref = self._client.collection(self.collection_name).document(str(data_object.id))
                await doc_ref.create(data_dict)
                
                self._logger.info(
                    "Created data object",
                    extra={
                        "object_id": str(data_object.id),
                        "execution_id": str(data_object.execution_id)
                    }
                )
                return data_object
            else:
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path=f"{self.collection_name}/{data_object.id}"
                )

        except Exception as e:
            self._logger.error(
                "Failed to create data object",
                extra={
                    "error": str(e),
                    "object_id": str(data_object.id)
                }
            )
            raise StorageException(
                "Data object creation failed",
                storage_path=f"{self.collection_name}/{data_object.id}"
            )

    async def get(self, data_object_id: DataObjectID) -> Optional[FirestoreDataObject]:
        """
        Retrieve data object by ID with error handling.
        
        Args:
            data_object_id: UUID of data object to retrieve
            
        Returns:
            FirestoreDataObject if found, None otherwise
            
        Raises:
            StorageException: If retrieval operation fails
        """
        try:
            if not self._circuit_open:
                doc_ref = self._client.collection(self.collection_name).document(str(data_object_id))
                doc = await doc_ref.get()
                
                if not doc.exists:
                    return None
                
                return FirestoreDataObject.from_dict(doc.to_dict())
            else:
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path=f"{self.collection_name}/{data_object_id}"
                )

        except Exception as e:
            self._logger.error(
                "Failed to retrieve data object",
                extra={
                    "error": str(e),
                    "object_id": str(data_object_id)
                }
            )
            raise StorageException(
                "Data object retrieval failed",
                storage_path=f"{self.collection_name}/{data_object_id}"
            )

    async def update(self, data_object: FirestoreDataObject) -> FirestoreDataObject:
        """
        Update existing data object with optimistic locking.
        
        Args:
            data_object: FirestoreDataObject instance to update
            
        Returns:
            Updated data object
            
        Raises:
            ValidationException: If data object validation fails
            StorageException: If update operation fails
        """
        try:
            if not await self.validate_entity(data_object):
                raise ValidationException(
                    "Data object validation failed",
                    {"object_id": str(data_object.id)}
                )

            if not self._circuit_open:
                # Implement optimistic locking
                @self._client.transaction()
                async def update_in_transaction(transaction):
                    doc_ref = self._client.collection(self.collection_name).document(str(data_object.id))
                    doc = await doc_ref.get()
                    
                    if not doc.exists:
                        raise ValidationException(
                            "Data object not found",
                            {"object_id": str(data_object.id)}
                        )
                    
                    # Update document
                    data_dict = data_object.to_dict()
                    transaction.update(doc_ref, data_dict)
                    return data_object

                return await update_in_transaction()
            else:
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path=f"{self.collection_name}/{data_object.id}"
                )

        except Exception as e:
            self._logger.error(
                "Failed to update data object",
                extra={
                    "error": str(e),
                    "object_id": str(data_object.id)
                }
            )
            raise StorageException(
                "Data object update failed",
                storage_path=f"{self.collection_name}/{data_object.id}"
            )

    async def delete(self, data_object_id: DataObjectID) -> bool:
        """
        Delete data object by ID with validation.
        
        Args:
            data_object_id: UUID of data object to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            StorageException: If deletion operation fails
        """
        try:
            if not self._circuit_open:
                doc_ref = self._client.collection(self.collection_name).document(str(data_object_id))
                await doc_ref.delete()
                
                self._logger.info(
                    "Deleted data object",
                    extra={"object_id": str(data_object_id)}
                )
                return True
            else:
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path=f"{self.collection_name}/{data_object_id}"
                )

        except Exception as e:
            self._logger.error(
                "Failed to delete data object",
                extra={
                    "error": str(e),
                    "object_id": str(data_object_id)
                }
            )
            raise StorageException(
                "Data object deletion failed",
                storage_path=f"{self.collection_name}/{data_object_id}"
            )

    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = 100,
        page_token: Optional[str] = None
    ) -> Tuple[List[FirestoreDataObject], Optional[str]]:
        """
        List data objects with filtering and pagination.
        
        Args:
            filters: Optional query filters
            limit: Maximum number of objects to return
            page_token: Token for pagination
            
        Returns:
            Tuple of (list of data objects, next page token)
            
        Raises:
            StorageException: If query operation fails
        """
        try:
            if not self._circuit_open:
                # Start with base query
                query = self._client.collection(self.collection_name)
                
                # Apply time-based partitioning
                current_partition = datetime.utcnow().strftime("%Y%m")
                query = query.where(filter=FieldFilter("partition_key", "==", current_partition))
                
                # Apply additional filters
                if filters:
                    for field, value in filters.items():
                        query = query.where(filter=FieldFilter(field, "==", value))
                
                # Apply pagination
                if page_token:
                    query = query.start_after(page_token)
                
                # Apply limit
                query = query.limit(limit)
                
                # Execute query
                docs = await query.get()
                
                # Convert to data objects
                objects = [FirestoreDataObject.from_dict(doc.to_dict()) for doc in docs]
                
                # Generate next page token
                next_token = docs[-1].id if len(objects) == limit else None
                
                return objects, next_token
            else:
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path=self.collection_name
                )

        except Exception as e:
            self._logger.error(
                "Failed to list data objects",
                extra={"error": str(e)}
            )
            raise StorageException(
                "Data object query failed",
                storage_path=self.collection_name
            )

    async def list_by_execution(self, execution_id: ExecutionID) -> List[FirestoreDataObject]:
        """
        List data objects for a specific task execution.
        
        Args:
            execution_id: UUID of the execution to query
            
        Returns:
            List of data objects for the execution
            
        Raises:
            StorageException: If query operation fails
        """
        try:
            if not self._circuit_open:
                query = (
                    self._client.collection(self.collection_name)
                    .where(filter=FieldFilter("execution_id", "==", str(execution_id)))
                )
                
                docs = await query.get()
                return [FirestoreDataObject.from_dict(doc.to_dict()) for doc in docs]
            else:
                raise StorageException(
                    "Circuit breaker is open",
                    storage_path=f"{self.collection_name}/execution/{execution_id}"
                )

        except Exception as e:
            self._logger.error(
                "Failed to list data objects by execution",
                extra={
                    "error": str(e),
                    "execution_id": str(execution_id)
                }
            )
            raise StorageException(
                "Execution data objects query failed",
                storage_path=f"{self.collection_name}/execution/{execution_id}"
            )

    async def validate_entity(self, data_object: FirestoreDataObject) -> bool:
        """
        Validate data object before database operations.
        
        Args:
            data_object: FirestoreDataObject instance to validate
            
        Returns:
            True if validation passes
            
        Raises:
            ValidationException: If validation fails
        """
        try:
            # Validate basic structure
            if not isinstance(data_object, FirestoreDataObject):
                raise ValidationException(
                    "Invalid data object type",
                    {
                        "expected": "FirestoreDataObject",
                        "received": type(data_object).__name__
                    }
                )
            
            # Validate required fields
            if not all([
                data_object.id,
                data_object.execution_id,
                data_object.storage_path,
                data_object.content_type,
                data_object.metadata
            ]):
                raise ValidationException(
                    "Missing required fields",
                    {"object_id": str(data_object.id)}
                )
            
            # Additional validation will be handled by FirestoreDataObject's own validation
            
            return True

        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                "Data object validation failed",
                {"error": str(e)}
            )