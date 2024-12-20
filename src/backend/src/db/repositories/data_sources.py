"""
Repository implementation for managing data source configurations in Cloud Firestore.

This module provides secure CRUD operations for data sources with enhanced security features
including credential encryption, access control, and comprehensive error handling.

Version: 1.0.0
"""

from typing import Dict, List, Optional, Tuple  # version: 3.11+
from datetime import datetime  # version: 3.11+
from uuid import UUID  # version: 3.11+
import logging  # version: 3.11+

from google.cloud import kms  # version: 2.11+
from google.cloud.firestore_v1.async_transaction import AsyncTransaction  # version: 2.11+

from db.repositories.base import BaseRepository
from db.models.data_source import DataSource
from core.exceptions import ValidationException, StorageException
from config.settings import settings

class DataSourceRepository(BaseRepository[DataSource]):
    """
    Repository implementation for secure data source management in Cloud Firestore.
    
    Provides CRUD operations with enhanced security features including:
    - Field-level encryption for sensitive credentials
    - Access control and audit logging
    - Optimistic locking for concurrent updates
    - Comprehensive error handling
    """

    def __init__(self) -> None:
        """Initialize repository with security configuration."""
        super().__init__("data_sources")
        self._logger = logging.getLogger(__name__)
        
        # Initialize KMS client for credential encryption
        self._kms_client = kms.KeyManagementServiceClient()
        self._key_name = settings.get_security_config()["encryption"]["key_name"]

    async def create(self, data_source: DataSource) -> DataSource:
        """
        Create a new data source with encrypted credentials.
        
        Args:
            data_source: DataSource instance to create
            
        Returns:
            Created DataSource with ID and encrypted credentials
            
        Raises:
            ValidationException: If validation fails
            StorageException: If creation fails
        """
        try:
            # Validate data source
            data_source.validate()
            
            # Check name uniqueness
            existing = await self.get_by_name(data_source.name)
            if existing:
                raise ValidationException(
                    "Data source name must be unique",
                    {"name": data_source.name}
                )
            
            # Encrypt sensitive credentials
            encrypted_credentials = await self._encrypt_credentials(data_source.credentials)
            
            # Prepare document data
            doc_data = {
                "id": str(data_source.id),
                "name": data_source.name,
                "type": data_source.type,
                "credentials": encrypted_credentials,
                "configuration": data_source.configuration,
                "metadata": data_source.metadata,
                "created_at": data_source.created_at,
                "updated_at": data_source.updated_at,
                "is_active": data_source.is_active
            }
            
            # Store in Firestore
            await self._client.collection(self.collection_name)\
                .document(str(data_source.id))\
                .create(doc_data)
            
            self._logger.info(
                f"Created data source: {data_source.id}",
                extra={"data_source_id": str(data_source.id)}
            )
            
            return data_source
            
        except Exception as e:
            self._logger.error(
                f"Failed to create data source: {str(e)}",
                extra={"data_source_id": str(data_source.id)}
            )
            raise

    async def get_by_name(self, name: str) -> Optional[DataSource]:
        """
        Retrieve data source by unique name.
        
        Args:
            name: Name of the data source
            
        Returns:
            DataSource if found, None otherwise
            
        Raises:
            StorageException: If retrieval fails
        """
        try:
            query = self._client.collection(self.collection_name)\
                .where("name", "==", name)\
                .limit(1)
            
            docs = await query.get()
            if not docs:
                return None
                
            doc_data = docs[0].to_dict()
            
            # Decrypt credentials before returning
            doc_data["credentials"] = await self._decrypt_credentials(doc_data["credentials"])
            
            return DataSource(**doc_data)
            
        except Exception as e:
            self._logger.error(
                f"Failed to get data source by name: {str(e)}",
                extra={"name": name}
            )
            raise

    async def list_by_type(
        self,
        source_type: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None
    ) -> Tuple[List[DataSource], Optional[str]]:
        """
        List data sources of specific type with pagination.
        
        Args:
            source_type: Type of sources to list ('scrape' or 'ocr')
            page_size: Optional number of items per page
            page_token: Optional pagination token
            
        Returns:
            Tuple of (list of DataSource objects, next page token)
            
        Raises:
            ValidationException: If source type is invalid
            StorageException: If query fails
        """
        try:
            if source_type not in ['scrape', 'ocr']:
                raise ValidationException(
                    "Invalid source type",
                    {"type": source_type}
                )
            
            # Build query
            query = self._client.collection(self.collection_name)\
                .where("type", "==", source_type)\
                .where("is_active", "==", True)
                
            if page_size:
                query = query.limit(page_size)
            if page_token:
                query = query.start_after({"id": page_token})
                
            # Execute query
            docs = await query.get()
            
            # Process results
            sources = []
            for doc in docs:
                data = doc.to_dict()
                data["credentials"] = await self._decrypt_credentials(data["credentials"])
                sources.append(DataSource(**data))
                
            # Generate next page token
            next_token = str(sources[-1].id) if len(sources) == page_size else None
            
            return sources, next_token
            
        except Exception as e:
            self._logger.error(
                f"Failed to list data sources: {str(e)}",
                extra={"type": source_type}
            )
            raise

    async def _encrypt_credentials(self, credentials: Dict) -> Dict:
        """
        Encrypt sensitive credential fields.
        
        Args:
            credentials: Dictionary of credentials to encrypt
            
        Returns:
            Dictionary with encrypted sensitive fields
            
        Raises:
            StorageException: If encryption fails
        """
        try:
            encrypted = credentials.copy()
            sensitive_fields = ["api_key", "password", "secret", "token", "service_account"]
            
            for field in sensitive_fields:
                if field in encrypted:
                    # Encrypt field value using KMS
                    response = await self._kms_client.encrypt(
                        request={
                            "name": self._key_name,
                            "plaintext": encrypted[field].encode(),
                        }
                    )
                    encrypted[field] = {
                        "encrypted_value": response.ciphertext,
                        "key_version": response.name
                    }
            
            return encrypted
            
        except Exception as e:
            raise StorageException(
                "Failed to encrypt credentials",
                storage_path="kms",
                storage_details={"error": str(e)}
            )

    async def _decrypt_credentials(self, encrypted_credentials: Dict) -> Dict:
        """
        Decrypt sensitive credential fields.
        
        Args:
            encrypted_credentials: Dictionary with encrypted fields
            
        Returns:
            Dictionary with decrypted sensitive fields
            
        Raises:
            StorageException: If decryption fails
        """
        try:
            decrypted = encrypted_credentials.copy()
            
            for field, value in decrypted.items():
                if isinstance(value, dict) and "encrypted_value" in value:
                    # Decrypt field value using KMS
                    response = await self._kms_client.decrypt(
                        request={
                            "name": value["key_version"],
                            "ciphertext": value["encrypted_value"],
                        }
                    )
                    decrypted[field] = response.plaintext.decode()
            
            return decrypted
            
        except Exception as e:
            raise StorageException(
                "Failed to decrypt credentials",
                storage_path="kms",
                storage_details={"error": str(e)}
            )

    async def validate_entity(self, entity: DataSource) -> bool:
        """
        Validate data source entity.
        
        Args:
            entity: DataSource instance to validate
            
        Returns:
            True if validation passes
            
        Raises:
            ValidationException: If validation fails
        """
        return entity.validate()