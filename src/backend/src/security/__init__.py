"""
Security module initialization providing core security components for the data processing pipeline.

This module exposes enterprise-grade security components including encryption, key management,
rate limiting, and token services. Implements comprehensive security controls following
industry best practices and compliance requirements.

Version: 1.0.0
"""

from typing import List

# Import core security components
from security.encryption import DataEncryption, EncryptionError
from security.key_management import KeyManager, KeyManagementError
from security.rate_limiter import RateLimiter, RateLimitExceeded
from security.token_service import TokenService, TokenError

# Module version
__version__ = "1.0.0"

# List of public exports
__all__: List[str] = [
    "DataEncryption",
    "EncryptionError",
    "KeyManager", 
    "KeyManagementError",
    "RateLimiter",
    "RateLimitExceeded",
    "TokenService",
    "TokenError"
]

# Security component documentation
DataEncryption.__doc__ = """
Enterprise-grade data encryption service using AES-256-GCM.

Provides secure data encryption and decryption capabilities with:
- AES-256-GCM authenticated encryption
- Secure IV generation and handling
- Key rotation support
- Thread-safe operations
"""

KeyManager.__doc__ = """
Secure key management service using Google Cloud KMS.

Features:
- Automated 90-day key rotation
- Secure key storage in Cloud KMS
- Thread-safe key operations
- Key version management
"""

RateLimiter.__doc__ = """
Distributed rate limiting service using Redis.

Implements:
- Sliding window rate limiting
- 1000 requests per hour default limit
- Per-client rate tracking
- Distributed rate limit enforcement
"""

TokenService.__doc__ = """
JWT token service with enhanced security features.

Provides:
- Secure token generation and validation
- Encrypted token claims
- Token refresh capabilities
- Token revocation and blacklisting
"""

# Error class documentation
EncryptionError.__doc__ = """
Exception raised for encryption-related errors.

Attributes:
    message: Human-readable error description
    error_code: Specific error code for the failure
"""

KeyManagementError.__doc__ = """
Exception raised for key management errors.

Attributes:
    message: Human-readable error description
    key_id: Identifier of the affected key
"""

RateLimitExceeded.__doc__ = """
Exception raised when rate limits are exceeded.

Attributes:
    message: Human-readable error description
    retry_after: Seconds until rate limit resets
"""

TokenError.__doc__ = """
Exception raised for token-related errors.

Attributes:
    message: Human-readable error description
    error_code: Specific token error code
    token_id: Affected token identifier
"""