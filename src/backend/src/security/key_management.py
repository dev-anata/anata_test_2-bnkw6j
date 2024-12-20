"""
Key management module for secure handling of encryption and signing keys.

This module implements secure key management functionality using Google Cloud KMS,
providing thread-safe operations, automated key rotation, and secure key storage.

Version: 1.0.0
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta  # version: 3.11+
from asyncio import AsyncLock  # version: 3.11+
import logging  # version: 3.11+
from google.cloud import kms_v1  # version: 2.18.0

from core.exceptions import PipelineException
from security.encryption import DataEncryption

# Constants for key management
KEY_ROTATION_DAYS = 30  # Days before key rotation
KEY_VERSION_STATES = ['ENABLED', 'DISABLED', 'DESTROYED']
KEY_PURPOSES = ['ENCRYPTION', 'SIGNING']
MAX_CACHE_SIZE = 100  # Maximum number of keys to cache


class KeyManagementError(PipelineException):
    """
    Custom exception for key management related errors.
    
    Provides detailed error information for key management operations while
    maintaining security by not exposing sensitive key material.
    
    Attributes:
        message (str): Human-readable error description
        original_error (Optional[Exception]): Original exception that caused the error
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize key management error with message and optional original error.
        
        Args:
            message: Human-readable error description
            original_error: Optional original exception that caused the error
        """
        super().__init__(message)
        self.original_error = original_error
        self._logger = logging.getLogger(__name__)
        
        error_msg = f"{message}"
        if original_error:
            error_msg += f" - Original error: {str(original_error)}"
        self._logger.error(error_msg)


class KeyManager:
    """
    Manages encryption and signing keys using Google Cloud KMS.
    
    Provides thread-safe key operations, automated key rotation, and secure
    key storage with caching for performance optimization.
    
    Attributes:
        _kms_client: Google Cloud KMS client
        _key_ring_path: Path to the key ring in Cloud KMS
        _active_keys: Cache of active keys with their creation timestamps
        _key_lock: Async lock for thread-safe operations
        _logger: Logger instance for key operations
    """
    
    def __init__(self, project_id: str, location_id: str) -> None:
        """
        Initialize key manager with GCP project and location.
        
        Args:
            project_id: Google Cloud project ID
            location_id: Google Cloud location ID (e.g., 'global')
        
        Raises:
            KeyManagementError: If initialization fails
        """
        try:
            self._kms_client = kms_v1.KeyManagementServiceClient()
            self._key_ring_path = (
                f"projects/{project_id}/locations/{location_id}/keyRings/pipeline-keys"
            )
            self._active_keys: Dict[str, Tuple[bytes, datetime]] = {}
            self._key_lock = AsyncLock()
            self._logger = logging.getLogger(__name__)
            
            # Ensure key ring exists
            self._ensure_key_ring_exists()
            
        except Exception as e:
            raise KeyManagementError("Failed to initialize key manager", e)
    
    async def get_active_key(self, key_purpose: str) -> bytes:
        """
        Get the currently active key for the specified purpose.
        
        Implements thread-safe access to keys with automatic rotation
        when needed based on key age.
        
        Args:
            key_purpose: Purpose of the key ('ENCRYPTION' or 'SIGNING')
            
        Returns:
            bytes: Active key for the specified purpose
            
        Raises:
            KeyManagementError: If key retrieval fails
        """
        if key_purpose not in KEY_PURPOSES:
            raise KeyManagementError(f"Invalid key purpose: {key_purpose}")
            
        try:
            async with self._key_lock:
                # Check cache first
                if key_purpose in self._active_keys:
                    key, timestamp = self._active_keys[key_purpose]
                    # Check if rotation is needed
                    if not await self.check_key_rotation(key_purpose):
                        return key
                
                # Generate new key if needed
                new_key = await self.rotate_key(key_purpose)
                return new_key
                
        except Exception as e:
            raise KeyManagementError(f"Failed to get active key for {key_purpose}", e)
    
    async def rotate_key(self, key_purpose: str) -> bytes:
        """
        Rotate the key for the specified purpose.
        
        Generates a new key, stores it in Cloud KMS, and updates the cache
        while properly cleaning up the old key.
        
        Args:
            key_purpose: Purpose of the key to rotate
            
        Returns:
            bytes: Newly generated and stored key
            
        Raises:
            KeyManagementError: If key rotation fails
        """
        try:
            # Generate new key
            new_key = DataEncryption.generate_key()
            
            # Create new key version in KMS
            key_path = f"{self._key_ring_path}/cryptoKeys/{key_purpose.lower()}"
            request = kms_v1.CreateCryptoKeyVersionRequest(
                parent=key_path,
                crypto_key_version={
                    "state": "ENABLED",
                    "algorithm": "GOOGLE_SYMMETRIC_ENCRYPTION"
                }
            )
            key_version = self._kms_client.create_crypto_key_version(request)
            
            # Store the key material
            self._store_key_material(key_version.name, new_key)
            
            # Update cache
            self._active_keys[key_purpose] = (new_key, datetime.utcnow())
            
            # Clean up old versions
            await self.cleanup_old_keys(key_purpose)
            
            self._logger.info(f"Successfully rotated key for {key_purpose}")
            return new_key
            
        except Exception as e:
            raise KeyManagementError(f"Failed to rotate key for {key_purpose}", e)
    
    async def check_key_rotation(self, key_purpose: str) -> bool:
        """
        Check if key rotation is needed based on age.
        
        Args:
            key_purpose: Purpose of the key to check
            
        Returns:
            bool: True if key rotation is needed
        """
        try:
            if key_purpose not in self._active_keys:
                return True
                
            _, timestamp = self._active_keys[key_purpose]
            age = datetime.utcnow() - timestamp
            needs_rotation = age.days >= KEY_ROTATION_DAYS
            
            if needs_rotation:
                self._logger.info(f"Key rotation needed for {key_purpose}")
                
            return needs_rotation
            
        except Exception as e:
            self._logger.error(f"Error checking key rotation: {str(e)}")
            return True
    
    async def cleanup_old_keys(self, key_purpose: str) -> None:
        """
        Clean up disabled and destroyed key versions.
        
        Args:
            key_purpose: Purpose of the keys to clean up
            
        Raises:
            KeyManagementError: If cleanup fails
        """
        try:
            key_path = f"{self._key_ring_path}/cryptoKeys/{key_purpose.lower()}"
            
            # List all versions
            request = kms_v1.ListCryptoKeyVersionsRequest(parent=key_path)
            versions = self._kms_client.list_crypto_key_versions(request)
            
            for version in versions:
                # Skip active version
                if version.state == "ENABLED":
                    continue
                    
                # Schedule destruction for disabled versions
                if version.state == "DISABLED":
                    destroy_request = kms_v1.DestroyCryptoKeyVersionRequest(
                        name=version.name
                    )
                    self._kms_client.destroy_crypto_key_version(destroy_request)
                    self._logger.info(f"Scheduled destruction for key version: {version.name}")
            
        except Exception as e:
            raise KeyManagementError(f"Failed to clean up old keys for {key_purpose}", e)
    
    def _ensure_key_ring_exists(self) -> None:
        """
        Ensure the key ring exists in Cloud KMS.
        
        Raises:
            KeyManagementError: If key ring creation fails
        """
        try:
            parent = self._key_ring_path.rsplit("/keyRings", 1)[0]
            request = kms_v1.CreateKeyRingRequest(
                parent=parent,
                key_ring_id="pipeline-keys"
            )
            self._kms_client.create_key_ring(request)
            self._logger.info("Created new key ring")
        except Exception as e:
            if "ALREADY_EXISTS" not in str(e):
                raise KeyManagementError("Failed to ensure key ring exists", e)
    
    def _store_key_material(self, key_version_name: str, key_material: bytes) -> None:
        """
        Store key material in Cloud KMS.
        
        Args:
            key_version_name: Full path to the key version
            key_material: Raw key material to store
            
        Raises:
            KeyManagementError: If key storage fails
        """
        try:
            request = kms_v1.ImportCryptoKeyVersionRequest(
                parent=key_version_name,
                algorithm="GOOGLE_SYMMETRIC_ENCRYPTION",
                import_job="",
                rsa_aes_wrapped_key=key_material
            )
            self._kms_client.import_crypto_key_version(request)
            
        except Exception as e:
            raise KeyManagementError("Failed to store key material", e)


__all__ = ['KeyManagementError', 'KeyManager']