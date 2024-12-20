"""
JWT token service implementing secure token generation, validation, and management.

This module provides enterprise-grade JWT token handling with enhanced security features
including encryption, key rotation, and comprehensive token lifecycle management.

Version: 1.0.0
"""

from datetime import datetime, timedelta  # version: 3.11+
from typing import Dict, Optional, List  # version: 3.11+
import threading  # version: 3.11+
import jwt  # version: 2.8.0

from core.exceptions import PipelineException
from security.encryption import DataEncryption
from security.key_management import KeyManager
from config.settings import settings

# Token configuration constants
TOKEN_TYPE = "Bearer"
ALGORITHM = "HS256"
MAX_TOKEN_ATTEMPTS = 3

# Thread-safe token blacklist
TOKEN_BLACKLIST = set()
_blacklist_lock = threading.Lock()


class TokenError(PipelineException):
    """
    Custom exception for token-related errors with detailed error categorization.

    Attributes:
        message (str): Human-readable error description
        error_code (str): Specific error code for categorization
        original_error (Optional[Exception]): Original exception if applicable
    """

    def __init__(self, message: str, error_code: str, original_error: Optional[Exception] = None) -> None:
        """Initialize token error with message and error code."""
        super().__init__(message, original_error)
        self.error_code = error_code


class TokenService:
    """
    Comprehensive service for JWT token lifecycle management with enhanced security features.

    Implements secure token generation, validation, and management with support for
    encryption, key rotation, and token blacklisting.

    Attributes:
        _key_manager (KeyManager): Key management service for token signing
        _encryption (DataEncryption): Encryption service for sensitive claims
        _lock (threading.Lock): Thread lock for concurrent operations
        _token_attempts (Dict[str, int]): Track token validation attempts
    """

    def __init__(self, key_manager: KeyManager) -> None:
        """
        Initialize token service with security components.

        Args:
            key_manager: Key management service for token operations
        """
        self._key_manager = key_manager
        self._encryption = DataEncryption(key_manager.get_active_key("SIGNING"))
        self._lock = threading.Lock()
        self._token_attempts = {}

    def generate_token(self, user_id: str, claims: Dict[str, any]) -> Dict[str, str]:
        """
        Generate secure JWT token with encryption and claims.

        Args:
            user_id: Unique identifier of the user
            claims: Additional claims to include in token

        Returns:
            Dict containing access and refresh tokens

        Raises:
            TokenError: If token generation fails
        """
        try:
            # Validate inputs
            if not user_id or not claims:
                raise TokenError("Invalid token parameters", "INVALID_PARAMETERS")

            # Get current timestamp
            now = datetime.utcnow()
            
            # Prepare token claims
            token_claims = {
                "sub": user_id,
                "iat": now,
                "exp": now + timedelta(seconds=settings.token_expiration),
                "type": "access"
            }
            token_claims.update(claims)

            # Encrypt sensitive claims
            sensitive_claims = {"roles": claims.get("roles", [])}
            encrypted_claims = self._encryption.encrypt(str(sensitive_claims).encode())
            token_claims["encrypted_data"] = encrypted_claims.hex()

            # Generate access token
            access_token = jwt.encode(
                token_claims,
                self._key_manager.get_active_key("SIGNING"),
                algorithm=ALGORITHM
            )

            # Generate refresh token with extended expiration
            refresh_claims = {
                "sub": user_id,
                "iat": now,
                "exp": now + timedelta(days=30),
                "type": "refresh"
            }
            refresh_token = jwt.encode(
                refresh_claims,
                self._key_manager.get_active_key("SIGNING"),
                algorithm=ALGORITHM
            )

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": TOKEN_TYPE,
                "expires_in": settings.token_expiration
            }

        except Exception as e:
            raise TokenError(f"Token generation failed: {str(e)}", "GENERATION_ERROR", e)

    def validate_token(self, token: str) -> Dict[str, any]:
        """
        Validate and decode JWT token with security checks.

        Args:
            token: JWT token to validate

        Returns:
            Dict containing decoded token claims

        Raises:
            TokenError: If token validation fails
        """
        try:
            # Check token blacklist
            with _blacklist_lock:
                if token in TOKEN_BLACKLIST:
                    raise TokenError("Token has been revoked", "TOKEN_REVOKED")

            # Check token attempts
            with self._lock:
                if token in self._token_attempts:
                    if self._token_attempts[token] >= MAX_TOKEN_ATTEMPTS:
                        raise TokenError("Maximum validation attempts exceeded", "MAX_ATTEMPTS")
                    self._token_attempts[token] += 1
                else:
                    self._token_attempts[token] = 1

            # Decode and validate token
            decoded = jwt.decode(
                token,
                self._key_manager.get_active_key("SIGNING"),
                algorithms=[ALGORITHM]
            )

            # Verify token type
            if decoded.get("type") != "access":
                raise TokenError("Invalid token type", "INVALID_TYPE")

            # Decrypt sensitive claims
            if "encrypted_data" in decoded:
                encrypted_data = bytes.fromhex(decoded["encrypted_data"])
                decrypted_data = self._encryption.decrypt(encrypted_data)
                decoded.update(eval(decrypted_data.decode()))

            return decoded

        except jwt.ExpiredSignatureError:
            raise TokenError("Token has expired", "TOKEN_EXPIRED")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Invalid token: {str(e)}", "INVALID_TOKEN", e)
        except Exception as e:
            raise TokenError(f"Token validation failed: {str(e)}", "VALIDATION_ERROR", e)

    def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Generate new access token from refresh token with security validation.

        Args:
            refresh_token: Valid refresh token

        Returns:
            Dict containing new access token

        Raises:
            TokenError: If token refresh fails
        """
        try:
            # Decode refresh token
            decoded = jwt.decode(
                refresh_token,
                self._key_manager.get_active_key("SIGNING"),
                algorithms=[ALGORITHM]
            )

            # Verify token type
            if decoded.get("type") != "refresh":
                raise TokenError("Invalid refresh token", "INVALID_REFRESH_TOKEN")

            # Generate new access token
            return self.generate_token(decoded["sub"], {})

        except Exception as e:
            raise TokenError(f"Token refresh failed: {str(e)}", "REFRESH_ERROR", e)

    def revoke_token(self, token: str) -> bool:
        """
        Revoke token and add to blacklist.

        Args:
            token: Token to revoke

        Returns:
            bool indicating success

        Raises:
            TokenError: If token revocation fails
        """
        try:
            # Validate token format
            jwt.decode(
                token,
                self._key_manager.get_active_key("SIGNING"),
                algorithms=[ALGORITHM]
            )

            # Add to blacklist
            with _blacklist_lock:
                TOKEN_BLACKLIST.add(token)

            # Clear validation attempts
            with self._lock:
                self._token_attempts.pop(token, None)

            return True

        except Exception as e:
            raise TokenError(f"Token revocation failed: {str(e)}", "REVOCATION_ERROR", e)


__all__ = ['TokenError', 'TokenService']