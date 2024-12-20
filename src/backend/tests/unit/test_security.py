"""
Unit tests for security components including encryption, key management, rate limiting,
and token services.

This module implements comprehensive test coverage for all security-related functionality
ensuring proper implementation of encryption, key rotation, rate limiting, and token
lifecycle management.

Version: 1.0.0
"""

import pytest  # version: 7.4+
from unittest.mock import MagicMock, Mock, patch  # version: 3.11+
from freezegun import freeze_time  # version: 1.2+
import time
from datetime import datetime, timedelta
import os
import json

from security.encryption import DataEncryption, EncryptionError
from security.key_management import KeyManager, KeyManagementError
from security.rate_limiter import RateLimiter, RateLimitExceeded
from security.token_service import TokenService, TokenError

def generate_test_key(key_size: int = 32) -> bytes:
    """Generate test encryption key for testing purposes."""
    if key_size <= 0:
        raise ValueError("Key size must be positive")
    return os.urandom(key_size)

def create_test_token_claims(custom_claims: dict = None) -> dict:
    """Create test JWT claims for token testing."""
    base_claims = {
        "sub": "test-user-123",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "roles": ["user", "admin"]
    }
    if custom_claims:
        base_claims.update(custom_claims)
    return base_claims

class TestDataEncryption:
    """Test suite for data encryption functionality."""

    def test_encryption_decryption_success(self):
        """Test successful encryption and decryption cycle."""
        # Generate test key and data
        key = generate_test_key()
        test_data = b"sensitive data for encryption test"
        
        # Initialize encryption
        encryption = DataEncryption(key)
        
        # Encrypt data
        encrypted_data = encryption.encrypt(test_data)
        assert encrypted_data != test_data
        assert len(encrypted_data) > len(test_data)
        
        # Decrypt data
        decrypted_data = encryption.decrypt(encrypted_data)
        assert decrypted_data == test_data

    def test_invalid_key_size(self):
        """Test encryption initialization with invalid key size."""
        invalid_key = generate_test_key(16)  # Wrong size
        
        with pytest.raises(EncryptionError) as exc_info:
            DataEncryption(invalid_key)
        assert "Invalid key size" in str(exc_info.value)

    def test_encryption_with_null_data(self):
        """Test encryption handling of null or empty data."""
        encryption = DataEncryption(generate_test_key())
        
        with pytest.raises(EncryptionError):
            encryption.encrypt(None)
            
        # Test empty bytes
        encrypted_empty = encryption.encrypt(b"")
        decrypted_empty = encryption.decrypt(encrypted_empty)
        assert decrypted_empty == b""

    @patch('security.encryption.os.urandom')
    def test_generate_key(self, mock_urandom):
        """Test encryption key generation."""
        mock_urandom.return_value = b"x" * 32
        key = DataEncryption.generate_key()
        assert len(key) == 32
        mock_urandom.assert_called_once_with(32)

class TestKeyManager:
    """Test suite for key management functionality."""

    @pytest.fixture
    def mock_kms_client(self):
        """Create mock KMS client for testing."""
        return MagicMock()

    def test_key_rotation(self, mock_kms_client):
        """Test key rotation functionality."""
        with patch('security.key_management.kms_v1.KeyManagementServiceClient', 
                  return_value=mock_kms_client):
            key_manager = KeyManager("test-project", "us-central1")
            
            # Setup mock responses
            mock_kms_client.create_crypto_key_version.return_value = MagicMock(
                name="projects/test-project/locations/us-central1/keyRings/pipeline-keys/cryptoKeys/test/cryptoKeyVersions/1"
            )
            
            # Test rotation
            new_key = key_manager.rotate_key("ENCRYPTION")
            assert len(new_key) == 32
            mock_kms_client.create_crypto_key_version.assert_called_once()

    def test_get_active_key(self, mock_kms_client):
        """Test retrieval of active encryption key."""
        with patch('security.key_management.kms_v1.KeyManagementServiceClient',
                  return_value=mock_kms_client):
            key_manager = KeyManager("test-project", "us-central1")
            
            # Setup mock key data
            test_key = generate_test_key()
            mock_kms_client.get_crypto_key_version.return_value = MagicMock(
                state="ENABLED",
                name="test-key-version"
            )
            
            # Test key retrieval
            active_key = key_manager.get_active_key("ENCRYPTION")
            assert len(active_key) == 32
            mock_kms_client.get_crypto_key_version.assert_called_once()

    def test_cleanup_old_keys(self, mock_kms_client):
        """Test cleanup of expired keys."""
        with patch('security.key_management.kms_v1.KeyManagementServiceClient',
                  return_value=mock_kms_client):
            key_manager = KeyManager("test-project", "us-central1")
            
            # Setup mock key versions
            mock_versions = [
                MagicMock(state="DISABLED", name="old-key-1"),
                MagicMock(state="ENABLED", name="active-key"),
                MagicMock(state="DISABLED", name="old-key-2")
            ]
            mock_kms_client.list_crypto_key_versions.return_value = mock_versions
            
            # Test cleanup
            key_manager.cleanup_old_keys("ENCRYPTION")
            assert mock_kms_client.destroy_crypto_key_version.call_count == 2

class TestRateLimiter:
    """Test suite for rate limiting functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client for testing."""
        return MagicMock()

    def test_rate_limit_exceeded(self, mock_redis):
        """Test rate limit enforcement."""
        with patch('security.rate_limiter.redis.Redis', return_value=mock_redis):
            rate_limiter = RateLimiter(max_requests=2, window_size=60)
            client_id = "test-client"
            
            # Mock Redis pipeline
            pipeline_mock = MagicMock()
            mock_redis.pipeline.return_value.__enter__.return_value = pipeline_mock
            pipeline_mock.execute.return_value = [3]  # Simulate exceeded requests
            
            with pytest.raises(RateLimitExceeded) as exc_info:
                rate_limiter.check_rate_limit(client_id)
            assert "Rate limit exceeded" in str(exc_info.value)

    def test_remaining_requests(self, mock_redis):
        """Test remaining requests calculation."""
        with patch('security.rate_limiter.redis.Redis', return_value=mock_redis):
            rate_limiter = RateLimiter(max_requests=10, window_size=60)
            client_id = "test-client"
            
            # Mock Redis pipeline responses
            pipeline_mock = MagicMock()
            mock_redis.pipeline.return_value.__enter__.return_value = pipeline_mock
            pipeline_mock.execute.return_value = [None, 5, [str(time.time() - 30)]]
            
            result = rate_limiter.get_remaining_requests(client_id)
            assert result["remaining_requests"] == 5
            assert "reset_time" in result

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_redis):
        """Test rate limiting under concurrent load."""
        with patch('security.rate_limiter.redis.Redis', return_value=mock_redis):
            rate_limiter = RateLimiter(max_requests=5, window_size=1)
            client_id = "test-client"
            
            # Mock Redis pipeline for concurrent testing
            pipeline_mock = MagicMock()
            mock_redis.pipeline.return_value.__enter__.return_value = pipeline_mock
            
            # Test concurrent access
            import asyncio
            tasks = [
                asyncio.create_task(
                    asyncio.to_thread(rate_limiter.check_rate_limit, client_id)
                ) for _ in range(10)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            assert sum(1 for r in results if isinstance(r, RateLimitExceeded)) > 0

class TestTokenService:
    """Test suite for JWT token service."""

    @pytest.fixture
    def token_service(self, mock_kms_client):
        """Create TokenService instance for testing."""
        with patch('security.key_management.kms_v1.KeyManagementServiceClient',
                  return_value=mock_kms_client):
            key_manager = KeyManager("test-project", "us-central1")
            return TokenService(key_manager)

    def test_token_generation(self, token_service):
        """Test JWT token generation."""
        claims = create_test_token_claims()
        
        token_pair = token_service.generate_token("test-user", claims)
        assert "access_token" in token_pair
        assert "refresh_token" in token_pair
        assert token_pair["token_type"] == "Bearer"
        assert token_pair["expires_in"] > 0

    def test_token_validation(self, token_service):
        """Test JWT token validation."""
        claims = create_test_token_claims()
        token_pair = token_service.generate_token("test-user", claims)
        
        # Test valid token
        decoded = token_service.validate_token(token_pair["access_token"])
        assert decoded["sub"] == "test-user"
        assert "roles" in decoded
        
        # Test expired token
        with freeze_time(datetime.utcnow() + timedelta(hours=2)):
            with pytest.raises(TokenError) as exc_info:
                token_service.validate_token(token_pair["access_token"])
            assert "expired" in str(exc_info.value)

    def test_token_refresh(self, token_service):
        """Test token refresh functionality."""
        claims = create_test_token_claims()
        token_pair = token_service.generate_token("test-user", claims)
        
        # Test refresh
        with freeze_time(datetime.utcnow() + timedelta(minutes=30)):
            new_tokens = token_service.refresh_token(token_pair["refresh_token"])
            assert "access_token" in new_tokens
            assert new_tokens["access_token"] != token_pair["access_token"]

    def test_token_revocation(self, token_service):
        """Test token revocation."""
        claims = create_test_token_claims()
        token_pair = token_service.generate_token("test-user", claims)
        
        # Revoke token
        assert token_service.revoke_token(token_pair["access_token"]) is True
        
        # Verify revoked token
        with pytest.raises(TokenError) as exc_info:
            token_service.validate_token(token_pair["access_token"])
        assert "revoked" in str(exc_info.value)