"""
Central application configuration module for the Data Processing Pipeline.

This module provides comprehensive configuration management with:
- Environment-specific configuration handling
- Enhanced validation and security controls
- Structured logging with sensitive data masking
- Configuration caching and performance optimization
- Robust error handling and validation

Version: 1.0.0
"""

from typing import Dict, Any, Optional, cast  # version: 3.11+
from pydantic import BaseModel, Field, validator  # version: 2.0+
from functools import lru_cache  # version: 3.11+

from config.settings import settings, ENV, DEBUG
from config.logging_config import setup_logging
from config.constants import (
    API_VERSION,
    DEFAULT_TIMEOUT_SECONDS,
    API_RATE_LIMIT_MAX_REQUESTS,
    API_RATE_LIMIT_WINDOW_SIZE
)

# Default configuration template
DEFAULT_CONFIG: Dict[str, Any] = {
    "api": {
        "version": API_VERSION,
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "rate_limit": {
            "max_requests": API_RATE_LIMIT_MAX_REQUESTS,
            "window_size": API_RATE_LIMIT_WINDOW_SIZE
        }
    },
    "storage": {
        "encryption": {
            "enabled": True,
            "algorithm": "AES-256-GCM",
            "key_rotation_days": 90
        },
        "retention": {
            "enabled": True,
            "days": 90
        }
    },
    "logging": {
        "level": "INFO",
        "structured": True,
        "mask_sensitive": True,
        "retention_days": 90
    }
}

class APIConfig(BaseModel):
    """API-specific configuration with validation."""
    version: str = Field(..., description="API version string")
    timeout: int = Field(..., ge=1, le=3600, description="API timeout in seconds")
    rate_limit: Dict[str, int] = Field(..., description="Rate limiting configuration")

    @validator("rate_limit")
    def validate_rate_limit(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Validate rate limiting configuration."""
        if "max_requests" not in v or "window_size" not in v:
            raise ValueError("Rate limit configuration must include max_requests and window_size")
        if v["max_requests"] < 1:
            raise ValueError("max_requests must be positive")
        if v["window_size"] < 1:
            raise ValueError("window_size must be positive")
        return v

class StorageConfig(BaseModel):
    """Storage-specific configuration with encryption settings."""
    encryption: Dict[str, Any] = Field(..., description="Storage encryption configuration")
    retention: Dict[str, Any] = Field(..., description="Data retention configuration")

    @validator("encryption")
    def validate_encryption(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate encryption configuration."""
        required_fields = {"enabled", "algorithm", "key_rotation_days"}
        if not all(field in v for field in required_fields):
            raise ValueError(f"Encryption config must include: {required_fields}")
        if v["enabled"] and v["algorithm"] not in {"AES-256-GCM", "AES-256-CBC"}:
            raise ValueError("Invalid encryption algorithm")
        return v

class LoggingConfig(BaseModel):
    """Logging configuration with data masking."""
    level: str = Field(..., description="Logging level")
    structured: bool = Field(..., description="Enable structured logging")
    mask_sensitive: bool = Field(..., description="Enable sensitive data masking")
    retention_days: int = Field(..., ge=1, description="Log retention period in days")

class AppConfig(BaseModel):
    """
    Main application configuration class with enhanced validation and security controls.
    
    Provides centralized configuration management with:
    - Environment-specific settings
    - Strict validation rules
    - Security controls
    - Configuration caching
    """
    
    env: str = Field(default=ENV, description="Environment name")
    debug: bool = Field(default=DEBUG, description="Debug mode flag")
    api_config: APIConfig = Field(..., description="API configuration")
    storage_config: StorageConfig = Field(..., description="Storage configuration")
    logging_config: LoggingConfig = Field(..., description="Logging configuration")
    config_version: str = Field(default="1.0.0", description="Configuration version")

    def __init__(self, config_override: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize application configuration with validation.

        Args:
            config_override: Optional configuration overrides
        """
        # Start with default configuration
        config = DEFAULT_CONFIG.copy()
        
        # Apply environment-specific settings
        config.update(self._get_env_config())
        
        # Apply any overrides
        if config_override:
            config = self._deep_merge(config, config_override)
        
        # Initialize parent class with validated config
        super().__init__(
            env=ENV,
            debug=DEBUG,
            api_config=config["api"],
            storage_config=config["storage"],
            logging_config=config["logging"]
        )
        
        # Initialize logging configuration
        self._setup_logging()

    def _get_env_config(self) -> Dict[str, Any]:
        """Get environment-specific configuration."""
        if self.env == "production":
            return {
                "logging": {"level": "INFO", "structured": True},
                "storage": {"encryption": {"key_rotation_days": 30}}
            }
        elif self.env == "staging":
            return {
                "logging": {"level": "DEBUG", "structured": True},
                "storage": {"encryption": {"key_rotation_days": 60}}
            }
        return {
            "logging": {"level": "DEBUG", "structured": False},
            "storage": {"encryption": {"key_rotation_days": 90}}
        }

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two configuration dictionaries.

        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary

        Returns:
            Merged configuration dictionary
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = AppConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _setup_logging(self) -> None:
        """Initialize enhanced logging configuration."""
        logging_config = {
            "level": self.logging_config.level,
            "structured": self.logging_config.structured,
            "enable_cloud_logging": self.env in {"production", "staging"},
            "retention_days": self.logging_config.retention_days
        }
        
        sensitive_patterns = {
            "password": r"\b[A-Za-z0-9._%+-]+\b",
            "api_key": r"\b[A-Za-z0-9-]{32,}\b",
            "token": r"\b[A-Za-z0-9-._~+/]+=*\b"
        }
        
        setup_logging(logging_config, sensitive_patterns)

    @lru_cache(maxsize=1)
    def get_api_config(self) -> Dict[str, Any]:
        """
        Get cached API configuration.

        Returns:
            API configuration dictionary
        """
        return self.api_config.dict()

    @lru_cache(maxsize=1)
    def get_storage_config(self) -> Dict[str, Any]:
        """
        Get cached storage configuration.

        Returns:
            Storage configuration dictionary
        """
        return self.storage_config.dict()

    @lru_cache(maxsize=1)
    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get cached logging configuration.

        Returns:
            Logging configuration dictionary
        """
        return self.logging_config.dict()

def load_config(config_override: Optional[Dict[str, Any]] = None) -> AppConfig:
    """
    Load and initialize application configuration.

    Args:
        config_override: Optional configuration overrides

    Returns:
        Initialized AppConfig instance
    """
    return AppConfig(config_override)

# Export configuration interface
__all__ = ["AppConfig", "load_config"]