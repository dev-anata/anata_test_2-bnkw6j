"""
Secure data encryption module implementing AES-256-GCM encryption for the data processing pipeline.

This module provides enterprise-grade encryption capabilities for securing sensitive data
using AES-256-GCM with proper IV handling, authentication, and secure key management.

Version: 1.0.0
"""

from typing import Optional
import os
from cryptography.hazmat.primitives.ciphers import (  # version: 41.0.0
    Cipher, algorithms, modes
)
from cryptography.hazmat.backends import default_backend  # version: 41.0.0
from core.exceptions import PipelineException

# Cryptographic constants
BLOCK_SIZE = 16  # AES block size in bytes
IV_SIZE = 12     # GCM mode IV size in bytes
TAG_SIZE = 16    # Authentication tag size in bytes
KEY_SIZE = 32    # AES-256 key size in bytes


class EncryptionError(PipelineException):
    """
    Custom exception for encryption and decryption related errors.
    
    Provides detailed error information for encryption operations while maintaining
    security by not exposing sensitive data in error messages.
    
    Attributes:
        message (str): Human-readable error description
        original_error (Optional[Exception]): Original exception that caused the error
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize encryption error with detailed message and original exception.
        
        Args:
            message: Human-readable error description
            original_error: Optional original exception that caused the error
        """
        super().__init__(message)
        self.original_error = original_error
        if original_error:
            self.message = f"{message} - Original error: {str(original_error)}"


class DataEncryption:
    """
    Handles encryption and decryption of data using AES-256-GCM.
    
    Implements secure data encryption with authenticated encryption using AES-256 in
    GCM mode, providing both confidentiality and authenticity of the encrypted data.
    
    Attributes:
        _key (bytes): Securely stored encryption key
    """
    
    def __init__(self, key: bytes) -> None:
        """
        Initialize encryption with provided key and validate key length.
        
        Args:
            key: 32-byte encryption key for AES-256
            
        Raises:
            EncryptionError: If key length is invalid
        """
        if len(key) != KEY_SIZE:
            raise EncryptionError(
                f"Invalid key size. Expected {KEY_SIZE} bytes, got {len(key)} bytes"
            )
        self._key = key
        self._backend = default_backend()

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using AES-256-GCM with authenticated encryption.
        
        Generates a random IV for each encryption operation and includes the IV
        and authentication tag with the encrypted data.
        
        Args:
            data: Raw data to encrypt
            
        Returns:
            bytes: Encrypted data with IV and authentication tag
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Generate random IV for this encryption operation
            iv = os.urandom(IV_SIZE)
            
            # Create cipher instance
            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(iv),
                backend=self._backend
            )
            encryptor = cipher.encryptor()
            
            # Encrypt data
            ciphertext = encryptor.update(data) + encryptor.finalize()
            
            # Combine IV + ciphertext + tag for storage/transmission
            encrypted_data = iv + ciphertext + encryptor.tag
            
            return encrypted_data
            
        except Exception as e:
            raise EncryptionError("Encryption failed", e)
        
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt data using AES-256-GCM with authentication verification.
        
        Extracts the IV and authentication tag from the encrypted data and verifies
        the authenticity before decryption.
        
        Args:
            encrypted_data: Combined IV + ciphertext + authentication tag
            
        Returns:
            bytes: Decrypted data
            
        Raises:
            EncryptionError: If decryption or authentication fails
        """
        try:
            # Validate minimum data length
            if len(encrypted_data) < IV_SIZE + TAG_SIZE:
                raise EncryptionError(
                    "Invalid encrypted data length - too short for IV and tag"
                )
            
            # Extract IV, ciphertext and tag
            iv = encrypted_data[:IV_SIZE]
            tag = encrypted_data[-TAG_SIZE:]
            ciphertext = encrypted_data[IV_SIZE:-TAG_SIZE]
            
            # Create cipher instance
            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(iv, tag),
                backend=self._backend
            )
            decryptor = cipher.decryptor()
            
            # Decrypt and verify data
            decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            return decrypted_data
            
        except Exception as e:
            raise EncryptionError("Decryption failed", e)

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new cryptographically secure random encryption key.
        
        Returns:
            bytes: Generated key of KEY_SIZE length
            
        Raises:
            EncryptionError: If key generation fails
        """
        try:
            key = os.urandom(KEY_SIZE)
            return key
        except Exception as e:
            raise EncryptionError("Key generation failed", e)


__all__ = ['EncryptionError', 'DataEncryption']