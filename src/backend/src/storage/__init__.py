"""
Storage package initialization module for the data processing pipeline.

This module provides a unified entry point for storage operations, exporting storage
backend implementations and interfaces that support both cloud and local storage
solutions. It implements the storage system requirements specified in the technical
specifications for managing data persistence across different storage backends.

Version: 1.0.0
"""

from storage.interfaces import StorageBackend
from storage.cloud_storage import CloudStorageBackend
from storage.local import LocalStorageBackend

# Export core storage components
__all__ = [
    'StorageBackend',      # Protocol interface for storage implementations
    'CloudStorageBackend', # Google Cloud Storage implementation
    'LocalStorageBackend'  # Local filesystem implementation for development
]

# Version information
__version__ = '1.0.0'
__author__ = 'Data Processing Pipeline Team'
__license__ = 'Proprietary'

# Storage backend configuration defaults
DEFAULT_CHUNK_SIZE = 256 * 1024  # 256KB chunk size for streaming operations
DEFAULT_STORAGE_REGION = 'us-central1'  # Default GCP region for cloud storage
DEFAULT_RETENTION_DAYS = 90  # Default retention period for stored objects