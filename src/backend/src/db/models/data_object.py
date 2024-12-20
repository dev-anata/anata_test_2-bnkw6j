"""
Firestore-specific implementation of the DataObject model.

This module extends the core DataObject model with Firestore-specific functionality
for storing and retrieving processed data metadata in Cloud Firestore.

Version: 1.0.0
"""

from dataclasses import dataclass, field  # version: 3.11+
from datetime import datetime  # version: 3.11+
from typing import Dict, Any  # version: 3.11+
from uuid import UUID, uuid4

from core.models import DataObject
from core.types import ExecutionID, DataObjectID, Metadata
from core.exceptions import ValidationException

@dataclass
class FirestoreDataObject(DataObject):
    """
    Firestore-specific implementation of DataObject model for storing processed data metadata.
    
    Extends the core DataObject model with Firestore-specific serialization and
    validation logic for Cloud Firestore storage.
    
    Attributes:
        id (DataObjectID): Unique identifier for the data object
        execution_id (ExecutionID): ID of the execution that created this object
        storage_path (str): GCS path where the data is stored
        content_type (str): MIME type of the stored data
        metadata (Metadata): Additional data attributes
        created_at (datetime): When the object was created
    """

    def __post_init__(self) -> None:
        """
        Validate and initialize Firestore-specific attributes.
        
        Performs additional validation for Firestore compatibility and
        ensures all fields are properly initialized.
        
        Raises:
            ValidationException: If any field validation fails
        """
        # Call parent validation first
        super().__post_init__()
        
        # Validate GCS storage path format
        if not self.storage_path.startswith('gs://'):
            raise ValidationException(
                "Invalid storage path format",
                {
                    "field": "storage_path",
                    "error": "Must be a valid GCS path starting with gs://"
                }
            )
        
        # Ensure metadata is JSON-serializable for Firestore
        try:
            # Attempt to validate metadata values are Firestore-compatible
            self._validate_metadata_types(self.metadata)
        except (TypeError, ValueError) as e:
            raise ValidationException(
                "Invalid metadata format for Firestore",
                {
                    "field": "metadata",
                    "error": str(e)
                }
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the data object to a Firestore-compatible dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation for Firestore storage
            
        Raises:
            ValidationException: If conversion to Firestore format fails
        """
        try:
            return {
                'id': str(self.id),  # Convert UUID to string
                'execution_id': str(self.execution_id),  # Convert UUID to string
                'storage_path': self.storage_path,
                'content_type': self.content_type,
                'metadata': self.metadata,  # Already validated as JSON-serializable
                'created_at': self.created_at,  # Firestore handles datetime natively
            }
        except Exception as e:
            raise ValidationException(
                "Failed to convert to Firestore format",
                {"error": str(e)}
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FirestoreDataObject':
        """
        Create a new FirestoreDataObject instance from a Firestore document.
        
        Args:
            data: Dictionary containing Firestore document data
            
        Returns:
            FirestoreDataObject: New instance initialized with document data
            
        Raises:
            ValidationException: If document data is invalid or incomplete
        """
        try:
            # Validate required fields
            required_fields = {'id', 'execution_id', 'storage_path', 'content_type', 'metadata', 'created_at'}
            missing_fields = required_fields - set(data.keys())
            if missing_fields:
                raise ValidationException(
                    "Missing required fields in Firestore document",
                    {"missing_fields": list(missing_fields)}
                )
            
            # Convert string IDs back to UUID objects
            object_id = UUID(data['id'])
            execution_id = UUID(data['execution_id'])
            
            # Create new instance
            return cls(
                id=object_id,
                execution_id=execution_id,
                storage_path=data['storage_path'],
                content_type=data['content_type'],
                metadata=data['metadata'],
                created_at=data['created_at']  # Firestore handles datetime conversion
            )
        except (ValueError, KeyError) as e:
            raise ValidationException(
                "Invalid Firestore document data",
                {"error": str(e)}
            )

    def _validate_metadata_types(self, metadata: Dict[str, Any]) -> None:
        """
        Validate that metadata values are Firestore-compatible types.
        
        Args:
            metadata: Dictionary of metadata to validate
            
        Raises:
            ValidationException: If any metadata value has an unsupported type
        """
        supported_types = (str, int, float, bool, datetime, dict, list)
        
        for key, value in metadata.items():
            if not isinstance(value, supported_types):
                raise ValidationException(
                    "Unsupported metadata value type",
                    {
                        "field": f"metadata.{key}",
                        "type": type(value).__name__,
                        "supported_types": [t.__name__ for t in supported_types]
                    }
                )
            
            # Recursively validate nested dictionaries
            if isinstance(value, dict):
                self._validate_metadata_types(value)
            # Validate list items
            elif isinstance(value, list):
                for item in value:
                    if not isinstance(item, supported_types):
                        raise ValidationException(
                            "Unsupported metadata list item type",
                            {
                                "field": f"metadata.{key}[]",
                                "type": type(item).__name__,
                                "supported_types": [t.__name__ for t in supported_types]
                            }
                        )