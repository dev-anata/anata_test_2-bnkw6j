"""
Unit tests for the configuration management system.

This module contains comprehensive test cases for validating the Settings class
functionality, environment handling, and configuration validation across different
deployment environments.

Version: 1.0.0
"""

import os
import pytest
from unittest.mock import patch, MagicMock  # version: 3.11+
from config.settings import Settings
from config.constants import (
    API_VERSION,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RETRIES,
    API_RATE_LIMIT_MAX_REQUESTS,
    STORAGE_BUCKET_NAME,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    LOG_RETENTION_DAYS,
    METRIC_COLLECTION_INTERVAL
)

class TestSettings:
    """Test suite for Settings configuration management system."""

    def setup_method(self):
        """Setup method run before each test case."""
        # Clear any existing environment variables that might affect tests
        self.env_vars = {
            "ENV": None,
            "DEBUG": None,
            "GCP_PROJECT_ID": None,
            "GCP_REGION": None,
            "STORAGE_BUCKET": None,
            "GCP_SERVICE_ACCOUNT_PATH": None,
            "GCP_EMULATOR_HOST": None
        }
        for var in self.env_vars:
            if var in os.environ:
                self.env_vars[var] = os.environ.pop(var)

    def teardown_method(self):
        """Cleanup method run after each test case."""
        # Restore original environment variables
        for var, value in self.env_vars.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_settings_default_values(self):
        """Test that settings loads with correct default values."""
        settings = Settings()
        
        # Test environment defaults
        assert settings.env == "development"
        assert settings.debug is False
        assert settings.api_version == API_VERSION
        
        # Test API configuration defaults
        assert settings.default_timeout == DEFAULT_TIMEOUT_SECONDS
        assert settings.max_retries == MAX_RETRIES
        assert settings.rate_limit_requests == API_RATE_LIMIT_MAX_REQUESTS
        
        # Test storage defaults
        assert settings.storage_bucket == STORAGE_BUCKET_NAME
        
        # Test pagination defaults
        assert settings.page_size == DEFAULT_PAGE_SIZE
        assert settings.max_page_size == MAX_PAGE_SIZE
        
        # Test monitoring defaults
        assert settings.log_retention == LOG_RETENTION_DAYS
        assert settings.metric_interval == METRIC_COLLECTION_INTERVAL

    def test_settings_environment_override(self, monkeypatch):
        """Test environment variable overrides for settings."""
        test_values = {
            "ENV": "production",
            "DEBUG": "true",
            "GCP_PROJECT_ID": "test-project",
            "GCP_REGION": "us-east1",
            "STORAGE_BUCKET": "custom-bucket",
            "DEFAULT_TIMEOUT_SECONDS": "600",
            "MAX_RETRIES": "5"
        }
        
        # Set test environment variables
        for key, value in test_values.items():
            monkeypatch.setenv(key, value)
        
        settings = Settings()
        
        # Verify overrides
        assert settings.env == "production"
        assert settings.debug is True
        assert settings.project_id == "test-project"
        assert settings.region == "us-east1"
        assert settings.storage_bucket == "custom-bucket"
        assert settings.default_timeout == 600
        assert settings.max_retries == 5

    def test_gcp_credentials_configuration(self, monkeypatch):
        """Test GCP credentials configuration and validation."""
        # Test production environment
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("GCP_PROJECT_ID", "prod-project")
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_PATH", "/path/to/service-account.json")
        
        settings = Settings()
        credentials = settings.get_gcp_credentials()
        
        assert credentials["project_id"] == "prod-project"
        assert credentials["service_account_path"] == "/path/to/service-account.json"
        assert credentials["use_compute_credentials"] is True
        
        # Test development environment
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("GCP_EMULATOR_HOST", "localhost:8085")
        
        settings = Settings()
        credentials = settings.get_gcp_credentials()
        
        assert credentials["use_compute_credentials"] is False
        assert credentials["emulator_host"] == "localhost:8085"

    def test_storage_configuration(self):
        """Test storage configuration settings."""
        settings = Settings()
        storage_config = settings.get_storage_config()
        
        assert storage_config["bucket_name"] == settings.storage_bucket
        assert storage_config["location"] == settings.region
        assert storage_config["storage_class"] == "REGIONAL"  # Development default
        assert isinstance(storage_config["lifecycle_rules"], list)
        assert storage_config["versioning_enabled"] is False  # Development default
        
        # Test production storage settings
        with patch.dict(os.environ, {"ENV": "production"}):
            settings = Settings()
            storage_config = settings.get_storage_config()
            
            assert storage_config["storage_class"] == "STANDARD"
            assert storage_config["versioning_enabled"] is True

    def test_monitoring_configuration(self):
        """Test monitoring configuration settings."""
        settings = Settings()
        monitoring_config = settings.get_monitoring_config()
        
        # Test logging configuration
        assert monitoring_config["logging"]["level"] == "DEBUG"  # Development default
        assert monitoring_config["logging"]["retention_days"] == settings.log_retention
        assert monitoring_config["logging"]["structured"] is True
        
        # Test metrics configuration
        assert monitoring_config["metrics"]["collection_interval"] == settings.metric_interval
        assert monitoring_config["metrics"]["retention_days"] == 7  # Development default
        
        # Test production monitoring settings
        with patch.dict(os.environ, {"ENV": "production"}):
            settings = Settings()
            monitoring_config = settings.get_monitoring_config()
            
            assert monitoring_config["logging"]["level"] == "INFO"
            assert monitoring_config["metrics"]["retention_days"] == 30

    def test_security_configuration(self):
        """Test security configuration settings."""
        settings = Settings()
        security_config = settings.get_security_config()
        
        # Test API key configuration
        assert security_config["api_key"]["length"] == settings.api_key_length
        assert security_config["api_key"]["rotation_days"] == 365  # Development default
        
        # Test token configuration
        assert security_config["token"]["expiration_seconds"] == settings.token_expiration
        assert security_config["token"]["algorithm"] == "HS256"
        
        # Test production security settings
        with patch.dict(os.environ, {"ENV": "production"}):
            settings = Settings()
            security_config = settings.get_security_config()
            
            assert security_config["api_key"]["rotation_days"] == 90
            assert security_config["encryption"]["key_rotation_period"] == "30d"

    def test_invalid_environment(self, monkeypatch):
        """Test error handling for invalid environment settings."""
        monkeypatch.setenv("ENV", "invalid_env")
        
        with pytest.raises(ValueError) as exc_info:
            settings = Settings()
            settings.get_storage_config()
        
        assert "invalid_env" in str(exc_info.value)

    def test_production_project_id_validation(self, monkeypatch):
        """Test project ID validation in production environment."""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("GCP_PROJECT_ID", "")
        
        with pytest.raises(ValueError) as exc_info:
            Settings()
        
        assert "GCP Project ID must be set in production environment" in str(exc_info.value)

    @pytest.mark.parametrize("page_size,expected", [
        (50, 50),
        (MAX_PAGE_SIZE + 1, MAX_PAGE_SIZE),
        (0, DEFAULT_PAGE_SIZE)
    ])
    def test_pagination_settings_validation(self, page_size, expected, monkeypatch):
        """Test pagination settings validation with various inputs."""
        monkeypatch.setenv("DEFAULT_PAGE_SIZE", str(page_size))
        
        settings = Settings()
        assert settings.page_size <= MAX_PAGE_SIZE
        assert settings.page_size == expected if page_size > MAX_PAGE_SIZE else page_size