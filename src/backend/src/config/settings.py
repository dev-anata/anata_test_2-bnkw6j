"""
Central configuration settings module for the Data Processing Pipeline.

This module manages environment-specific configuration, application settings,
and cloud service integrations using Pydantic for validation. It provides
a single source of truth for all application configuration parameters.

Version: 1.0.0
"""

import os  # version: 3.11+
from typing import Dict, Any, Optional  # version: 3.11+
from pydantic import BaseSettings, Field, validator  # version: 2.0+
from dotenv import load_dotenv  # version: 1.0+

from config.constants import (
    API_VERSION,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    API_RATE_LIMIT_MAX_REQUESTS,
    API_RATE_LIMIT_WINDOW_SIZE,
    TOKEN_EXPIRATION_SECONDS,
    API_KEY_LENGTH,
    STORAGE_BUCKET_NAME,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    LOG_RETENTION_DAYS,
    METRIC_COLLECTION_INTERVAL,
)
from core.types import TaskType, TaskStatus, DataSourceID

# Load environment variables from .env file if present
load_dotenv()

# Global environment configuration
ENV: str = os.getenv("ENV", "development")
DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
CONFIG_FILE_PATH: str = os.getenv("CONFIG_FILE_PATH", ".env")

class Settings(BaseSettings):
    """
    Main settings class using Pydantic for validation and environment management.
    Handles all application configuration including GCP settings, security configuration,
    and environment-specific parameters.
    """

    # Environment Configuration
    env: str = Field(default=ENV, env="ENV")
    debug: bool = Field(default=DEBUG, env="DEBUG")
    
    # GCP Configuration
    project_id: str = Field(
        default=os.getenv("GCP_PROJECT_ID", ""),
        env="GCP_PROJECT_ID",
        description="Google Cloud Project ID"
    )
    region: str = Field(
        default=os.getenv("GCP_REGION", "us-central1"),
        env="GCP_REGION",
        description="Google Cloud Region"
    )
    
    # Storage Configuration
    storage_bucket: str = Field(
        default=os.getenv("STORAGE_BUCKET", STORAGE_BUCKET_NAME),
        env="STORAGE_BUCKET",
        description="GCS Bucket Name"
    )
    
    # API Configuration
    api_version: int = Field(default=API_VERSION, env="API_VERSION")
    default_timeout: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        env="DEFAULT_TIMEOUT_SECONDS"
    )
    max_retries: int = Field(default=MAX_RETRIES, env="MAX_RETRIES")
    retry_backoff: float = Field(
        default=RETRY_BACKOFF_FACTOR,
        env="RETRY_BACKOFF_FACTOR"
    )
    
    # Rate Limiting
    rate_limit_requests: int = Field(
        default=API_RATE_LIMIT_MAX_REQUESTS,
        env="API_RATE_LIMIT_MAX_REQUESTS"
    )
    rate_limit_window: int = Field(
        default=API_RATE_LIMIT_WINDOW_SIZE,
        env="API_RATE_LIMIT_WINDOW_SIZE"
    )
    
    # Security Configuration
    token_expiration: int = Field(
        default=TOKEN_EXPIRATION_SECONDS,
        env="TOKEN_EXPIRATION_SECONDS"
    )
    api_key_length: int = Field(
        default=API_KEY_LENGTH,
        env="API_KEY_LENGTH"
    )
    
    # Pagination Settings
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, env="DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=MAX_PAGE_SIZE, env="MAX_PAGE_SIZE")
    
    # Monitoring Configuration
    log_retention: int = Field(
        default=LOG_RETENTION_DAYS,
        env="LOG_RETENTION_DAYS"
    )
    metric_interval: int = Field(
        default=METRIC_COLLECTION_INTERVAL,
        env="METRIC_COLLECTION_INTERVAL"
    )

    @validator("project_id")
    def validate_project_id(cls, v: str) -> str:
        """Validate GCP project ID is provided in production."""
        if ENV == "production" and not v:
            raise ValueError("GCP Project ID must be set in production environment")
        return v

    def get_gcp_credentials(self) -> Dict[str, Any]:
        """
        Get GCP credentials configuration based on environment.
        
        Returns:
            Dict[str, Any]: GCP credentials configuration including service account
            and project settings.
        """
        credentials_config = {
            "project_id": self.project_id,
            "region": self.region,
        }

        if self.env == "production":
            credentials_config.update({
                "service_account_path": os.getenv("GCP_SERVICE_ACCOUNT_PATH"),
                "use_compute_credentials": True,
            })
        else:
            credentials_config.update({
                "use_compute_credentials": False,
                "emulator_host": os.getenv("GCP_EMULATOR_HOST"),
            })

        return credentials_config

    def get_storage_config(self) -> Dict[str, Any]:
        """
        Get storage configuration settings for GCS.
        
        Returns:
            Dict[str, Any]: Storage configuration including bucket and options.
        """
        storage_config = {
            "bucket_name": self.storage_bucket,
            "location": self.region,
            "storage_class": "STANDARD" if self.env == "production" else "REGIONAL",
            "lifecycle_rules": [
                {
                    "action": {"type": "Delete"},
                    "condition": {"age": self.log_retention},
                }
            ],
            "versioning_enabled": self.env == "production",
        }

        return storage_config

    def get_security_config(self) -> Dict[str, Any]:
        """
        Get security configuration settings.
        
        Returns:
            Dict[str, Any]: Security configuration including API and encryption settings.
        """
        security_config = {
            "api_key": {
                "length": self.api_key_length,
                "rotation_days": 90 if self.env == "production" else 365,
            },
            "token": {
                "expiration_seconds": self.token_expiration,
                "algorithm": "HS256",
            },
            "encryption": {
                "algorithm": "AES-256-GCM",
                "key_rotation_period": "30d" if self.env == "production" else "90d",
            },
            "rate_limiting": {
                "max_requests": self.rate_limit_requests,
                "window_size": self.rate_limit_window,
            },
        }

        return security_config

    def get_monitoring_config(self) -> Dict[str, Any]:
        """
        Get monitoring configuration settings.
        
        Returns:
            Dict[str, Any]: Monitoring configuration including logging and metrics.
        """
        monitoring_config = {
            "logging": {
                "level": "INFO" if self.env == "production" else "DEBUG",
                "retention_days": self.log_retention,
                "structured": True,
            },
            "metrics": {
                "collection_interval": self.metric_interval,
                "retention_days": 30 if self.env == "production" else 7,
            },
            "alerts": {
                "error_rate_threshold": 0.01,
                "latency_threshold_ms": 500,
                "resource_utilization_threshold": 0.8,
            },
        }

        return monitoring_config

    class Config:
        """Pydantic configuration class."""
        env_file = CONFIG_FILE_PATH
        env_file_encoding = "utf-8"
        case_sensitive = True

# Create a global settings instance
settings = Settings()

# Export commonly used settings
__all__ = [
    "settings",
    "ENV",
    "DEBUG",
]