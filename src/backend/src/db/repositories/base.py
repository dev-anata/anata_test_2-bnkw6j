"""
Abstract base repository class for database operations.

Provides a standardized interface for database operations with comprehensive error handling,
retry logic, and validation. Implements the repository pattern for Firestore database access.

Version: 1.0.0
"""

from abc import ABC, abstractmethod  # version: 3.11+
from typing import Dict, List, Optional, TypeVar, Generic, Any  # version: 3.11+
from uuid import UUID  # version: 3.11+
import logging  # version: 3.11+

from tenacity import (  # version: 8.2+
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from circuitbreaker import CircuitBreaker  # version: 1.4+

from core.models import Task, TaskExecution, DataObject
from db.firestore import get_firestore_client, FirestoreError
from core.exceptions import PipelineException, StorageError

# Type variable for generic repository
T = TypeVar('T')

# Repository configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0
BATCH_SIZE = 500
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60

class BaseRepository(Generic[T], ABC):
    """
    Abstract base repository implementing common database operations.
    
    Provides standardized CRUD operations with error handling, retry logic,
    and validation for Firestore database access.
    
    Type Parameters:
        T: The entity type this repository manages (Task, TaskExecution, or DataObject)
    """

    def __init__(self, collection_name: str) -> None:
        """
        Initialize repository with collection name and setup error handling.
        
        Args:
            collection_name: Name of the Firestore collection
        """
        self._logger = logging.getLogger(__name__)
        self.collection_name = collection_name
        self._client = get_firestore_client()
        
        # Configure circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            expected_exception=FirestoreError
        )

    @abstractmethod
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_DELAY),
        retry=retry_if_exception_type(FirestoreError)
    )
    async def create(self, entity: T) -> T:
        """
        Create a new entity in the database.
        
        Args:
            entity: Entity instance to create
            
        Returns:
            Created entity with assigned ID
            
        Raises:
            StorageError: If creation fails
            ValidationError: If entity validation fails
        """
        pass

    @abstractmethod
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_DELAY),
        retry=retry_if_exception_type(FirestoreError)
    )
    async def get(self, entity_id: UUID) -> Optional[T]:
        """
        Retrieve an entity by ID.
        
        Args:
            entity_id: UUID of entity to retrieve
            
        Returns:
            Entity if found, None otherwise
            
        Raises:
            StorageError: If retrieval fails
        """
        pass

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_DELAY),
        retry=retry_if_exception_type(FirestoreError)
    )
    async def update(self, entity: T) -> T:
        """
        Update an existing entity.
        
        Args:
            entity: Entity instance to update
            
        Returns:
            Updated entity
            
        Raises:
            StorageError: If update fails
            ValidationError: If entity validation fails
        """
        try:
            if not await self.validate_entity(entity):
                raise ValueError("Entity validation failed")

            entity_dict = self._to_dict(entity)
            await self._circuit_breaker.call(
                self._client.collection(self.collection_name)
                .document(str(entity_dict['id']))
                .update(entity_dict)
            )
            return entity

        except FirestoreError as e:
            self._logger.error(f"Failed to update entity: {str(e)}")
            raise StorageError(f"Update failed: {str(e)}")
        except Exception as e:
            self._logger.error(f"Unexpected error during update: {str(e)}")
            raise PipelineException(f"Update error: {str(e)}")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_DELAY),
        retry=retry_if_exception_type(FirestoreError)
    )
    async def delete(self, entity_id: UUID) -> None:
        """
        Delete an entity by ID.
        
        Args:
            entity_id: UUID of entity to delete
            
        Raises:
            StorageError: If deletion fails
        """
        try:
            await self._circuit_breaker.call(
                self._client.collection(self.collection_name)
                .document(str(entity_id))
                .delete()
            )
        except FirestoreError as e:
            self._logger.error(f"Failed to delete entity: {str(e)}")
            raise StorageError(f"Deletion failed: {str(e)}")
        except Exception as e:
            self._logger.error(f"Unexpected error during deletion: {str(e)}")
            raise PipelineException(f"Deletion error: {str(e)}")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_DELAY),
        retry=retry_if_exception_type(FirestoreError)
    )
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List entities with optional filtering and pagination.
        
        Args:
            filters: Optional query filters
            page_size: Number of items per page
            page_token: Token for pagination
            
        Returns:
            Dict containing entities and pagination info
            
        Raises:
            StorageError: If query fails
        """
        try:
            query = self._client.collection(self.collection_name)
            
            if filters:
                for field, value in filters.items():
                    query = query.where(field, "==", value)
            
            query = query.limit(page_size)
            
            if page_token:
                query = query.start_after(page_token)
            
            docs = await self._circuit_breaker.call(query.get())
            
            entities = [self._from_dict(doc.to_dict()) for doc in docs]
            next_page_token = docs[-1].id if len(docs) == page_size else None
            
            return {
                "items": entities,
                "next_page_token": next_page_token
            }

        except FirestoreError as e:
            self._logger.error(f"Failed to list entities: {str(e)}")
            raise StorageError(f"List operation failed: {str(e)}")
        except Exception as e:
            self._logger.error(f"Unexpected error during list operation: {str(e)}")
            raise PipelineException(f"List operation error: {str(e)}")

    async def batch_create(self, entities: List[T]) -> List[T]:
        """
        Create multiple entities in a batch operation.
        
        Args:
            entities: List of entities to create
            
        Returns:
            List of created entities
            
        Raises:
            StorageError: If batch creation fails
            ValidationError: If validation fails for any entity
        """
        if len(entities) > BATCH_SIZE:
            raise ValueError(f"Batch size exceeds maximum of {BATCH_SIZE}")

        try:
            batch = self._client.batch()
            created_entities = []

            for entity in entities:
                if not await self.validate_entity(entity):
                    raise ValueError(f"Validation failed for entity: {entity}")
                
                entity_dict = self._to_dict(entity)
                ref = self._client.collection(self.collection_name).document()
                batch.create(ref, entity_dict)
                created_entities.append(entity)

            await self._circuit_breaker.call(batch.commit())
            return created_entities

        except FirestoreError as e:
            self._logger.error(f"Failed to create entities in batch: {str(e)}")
            raise StorageError(f"Batch creation failed: {str(e)}")
        except Exception as e:
            self._logger.error(f"Unexpected error during batch creation: {str(e)}")
            raise PipelineException(f"Batch creation error: {str(e)}")

    @abstractmethod
    async def validate_entity(self, entity: T) -> bool:
        """
        Validate entity data before database operations.
        
        Args:
            entity: Entity to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        pass

    def _to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary for storage."""
        if isinstance(entity, (Task, TaskExecution, DataObject)):
            return {
                'id': str(entity.id),
                **{k: v for k, v in entity.__dict__.items() if k != 'id'}
            }
        raise ValueError(f"Unsupported entity type: {type(entity)}")

    def _from_dict(self, data: Dict[str, Any]) -> T:
        """Convert dictionary to entity instance."""
        if not data:
            return None
        
        entity_type = self._get_entity_type()
        return entity_type(**data)

    def _get_entity_type(self) -> type:
        """Get the concrete entity type for this repository."""
        return self.__orig_bases__[0].__args__[0]