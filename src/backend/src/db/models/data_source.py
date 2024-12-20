"""
Data source model for managing configurations of web scraping and OCR processing sources.

This module provides a structured data model for storing and validating data source
configurations used in the data processing pipeline. It ensures proper validation
and management of source configurations for both web scraping and OCR tasks.

Version: 1.0.0
"""

from dataclasses import dataclass, field  # version: 3.11+
from datetime import datetime  # version: 3.11+
from uuid import UUID, uuid4  # version: 3.11+
from typing import Dict, Optional, Any  # version: 3.11+

from core.types import DataSourceID, Metadata
from core.exceptions import ValidationException


@dataclass
class DataSource:
    """
    Model representing a data source configuration for scraping or OCR tasks.
    
    Attributes:
        id (UUID): Unique identifier for the data source
        name (str): Human-readable name of the data source
        type (str): Type of data source ('scrape' or 'ocr')
        credentials (Dict[str, Any]): Authentication credentials for the source
        configuration (Dict[str, Any]): Source-specific configuration parameters
        metadata (Metadata): Additional metadata about the data source
        created_at (datetime): Timestamp when the source was created
        updated_at (Optional[datetime]): Timestamp of last update
        is_active (bool): Whether the source is currently active
    """
    
    name: str
    type: str
    credentials: Dict[str, Any]
    configuration: Dict[str, Any]
    metadata: Metadata
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_active: bool = True

    def __post_init__(self) -> None:
        """
        Perform post-initialization validation of the data source.
        
        Raises:
            ValidationException: If the data source configuration is invalid
        """
        self.validate()

    def validate(self) -> bool:
        """
        Validate the data source configuration.
        
        Validates source type, required fields, credentials format, and configuration schema.
        
        Returns:
            bool: True if validation passes
            
        Raises:
            ValidationException: If validation fails with detailed error information
        """
        validation_errors: Dict[str, Any] = {}

        # Validate source type
        if self.type not in ['scrape', 'ocr']:
            validation_errors['type'] = f"Invalid source type: {self.type}. Must be 'scrape' or 'ocr'"

        # Validate name
        if not self.name or not isinstance(self.name, str):
            validation_errors['name'] = "Name is required and must be a string"

        # Validate credentials
        if not isinstance(self.credentials, dict):
            validation_errors['credentials'] = "Credentials must be a dictionary"
        elif self.type == 'scrape' and 'api_key' not in self.credentials:
            validation_errors['credentials'] = "API key is required for scraping sources"
        elif self.type == 'ocr' and 'service_account' not in self.credentials:
            validation_errors['credentials'] = "Service account credentials required for OCR sources"

        # Validate configuration
        if not isinstance(self.configuration, dict):
            validation_errors['configuration'] = "Configuration must be a dictionary"
        elif self.type == 'scrape' and 'base_url' not in self.configuration:
            validation_errors['configuration'] = "Base URL is required for scraping sources"
        elif self.type == 'ocr' and 'output_format' not in self.configuration:
            validation_errors['configuration'] = "Output format is required for OCR sources"

        # Validate metadata
        if not isinstance(self.metadata, dict):
            validation_errors['metadata'] = "Metadata must be a dictionary"
        elif 'content_type' not in self.metadata:
            validation_errors['metadata'] = "Content type is required in metadata"

        if validation_errors:
            raise ValidationException(
                message="Data source validation failed",
                validation_errors=validation_errors
            )

        return True

    def update_configuration(self, new_configuration: Dict[str, Any]) -> None:
        """
        Update the data source configuration.
        
        Args:
            new_configuration: New configuration dictionary to apply
            
        Raises:
            ValidationException: If the new configuration is invalid
        """
        # Create temporary copy with new configuration for validation
        temp_config = self.configuration.copy()
        temp_config.update(new_configuration)
        
        # Store original configuration in case validation fails
        original_config = self.configuration.copy()
        
        # Apply new configuration temporarily and validate
        self.configuration = temp_config
        try:
            self.validate()
        except ValidationException as e:
            # Restore original configuration if validation fails
            self.configuration = original_config
            raise ValidationException(
                message="Invalid configuration update",
                validation_errors=e.validation_errors
            )

        # Update timestamp after successful validation
        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        """
        Deactivate the data source.
        
        Sets is_active to False and updates the updated_at timestamp.
        """
        self.is_active = False
        self.updated_at = datetime.utcnow()