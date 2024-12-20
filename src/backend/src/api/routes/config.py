"""
Configuration management route handler implementing secure system configuration access.

This module provides API endpoints for viewing and modifying system configuration with:
- Role-based access control
- Configuration validation
- Audit logging
- Response caching
- Comprehensive error handling

Version: 1.0.0
"""

from datetime import datetime  # version: 3.11+
from typing import Dict, Optional  # version: 3.11+
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks  # version: 0.100+
from pydantic import BaseModel, Field, validator  # version: 2.0+
from fastapi_cache import Cache  # version: 0.1+
import structlog  # version: 23.1+

from config.app_config import AppConfig
from api.dependencies import verify_admin_role
from core.exceptions import ConfigurationException, ValidationException

# Configure structured logger
logger = structlog.get_logger(__name__)

# Router configuration
router = APIRouter(prefix="/api/v1/config", tags=["config"])

# Constants
CONFIG_CACHE_TTL = 300  # 5 minutes cache TTL
MAX_CONFIG_SIZE = 1048576  # 1MB max config size

class ConfigResponse(BaseModel):
    """
    Response model for configuration data with validation.
    
    Attributes:
        api_config: API-specific configuration settings
        storage_config: Storage-specific configuration settings
        environment: Current environment name
        version: Configuration version string
        last_modified: Timestamp of last modification
    """
    api_config: Dict = Field(..., description="API configuration settings")
    storage_config: Dict = Field(..., description="Storage configuration settings")
    environment: str = Field(..., description="Environment name")
    version: str = Field(..., description="Configuration version")
    last_modified: datetime = Field(default_factory=datetime.utcnow)

    @validator("api_config", "storage_config")
    def validate_config(cls, value: Dict) -> Dict:
        """Validate configuration data against schema."""
        if not isinstance(value, dict):
            raise ValueError("Configuration must be a dictionary")
        
        # Validate size constraints
        if len(str(value)) > MAX_CONFIG_SIZE:
            raise ValueError(f"Configuration size exceeds {MAX_CONFIG_SIZE} bytes")
            
        return value

class ConfigUpdateRequest(BaseModel):
    """
    Request model for configuration updates with validation.
    
    Attributes:
        api_config: Updated API configuration
        storage_config: Updated storage configuration
    """
    api_config: Optional[Dict] = Field(None, description="API configuration updates")
    storage_config: Optional[Dict] = Field(None, description="Storage configuration updates")

    @validator("api_config", "storage_config")
    def validate_update(cls, value: Optional[Dict]) -> Optional[Dict]:
        """Validate configuration update data."""
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError("Configuration must be a dictionary")
                
            # Validate size constraints
            if len(str(value)) > MAX_CONFIG_SIZE:
                raise ValueError(f"Configuration size exceeds {MAX_CONFIG_SIZE} bytes")
                
            # Validate required fields are not removed
            required_fields = {"version", "enabled"}
            if any(field not in value for field in required_fields):
                raise ValueError(f"Cannot remove required fields: {required_fields}")
                
        return value

@router.get("/", response_model=ConfigResponse)
@Cache(expire=CONFIG_CACHE_TTL)
async def get_config(
    user: Dict = Depends(verify_admin_role),
    background_tasks: BackgroundTasks = None
) -> ConfigResponse:
    """
    Get current system configuration with caching.
    
    Args:
        user: Verified admin user from dependency
        background_tasks: FastAPI background tasks
        
    Returns:
        ConfigResponse: Current system configuration
        
    Raises:
        HTTPException: If configuration retrieval fails
    """
    try:
        # Get current configuration
        app_config = AppConfig()
        
        # Build response
        config_response = ConfigResponse(
            api_config=app_config.get_api_config(),
            storage_config=app_config.get_storage_config(),
            environment=app_config.env,
            version=app_config.config_version,
            last_modified=datetime.utcnow()
        )
        
        # Log access
        logger.info(
            "Configuration retrieved",
            user_id=user.get("id"),
            environment=app_config.env
        )
        
        return config_response
        
    except ConfigurationException as e:
        logger.error(
            "Configuration retrieval failed",
            error=str(e),
            user_id=user.get("id")
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve configuration: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Unexpected error retrieving configuration",
            error=str(e),
            user_id=user.get("id")
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.put("/", response_model=ConfigResponse)
async def update_config(
    user: Dict = Depends(verify_admin_role),
    config_update: ConfigUpdateRequest = None,
    background_tasks: BackgroundTasks = None
) -> ConfigResponse:
    """
    Update system configuration with validation.
    
    Args:
        user: Verified admin user from dependency
        config_update: Configuration update request
        background_tasks: FastAPI background tasks
        
    Returns:
        ConfigResponse: Updated system configuration
        
    Raises:
        HTTPException: If update fails
    """
    try:
        # Get current configuration
        app_config = AppConfig()
        
        # Apply updates
        if config_update.api_config:
            app_config.update_api_config(config_update.api_config)
            
        if config_update.storage_config:
            app_config.update_storage_config(config_update.storage_config)
            
        # Build response
        updated_config = ConfigResponse(
            api_config=app_config.get_api_config(),
            storage_config=app_config.get_storage_config(),
            environment=app_config.env,
            version=app_config.config_version,
            last_modified=datetime.utcnow()
        )
        
        # Log update
        logger.info(
            "Configuration updated",
            user_id=user.get("id"),
            environment=app_config.env,
            updates={
                "api": bool(config_update.api_config),
                "storage": bool(config_update.storage_config)
            }
        )
        
        return updated_config
        
    except ValidationException as e:
        logger.error(
            "Configuration validation failed",
            error=str(e),
            user_id=user.get("id")
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration: {str(e)}"
        )
    except ConfigurationException as e:
        logger.error(
            "Configuration update failed",
            error=str(e),
            user_id=user.get("id")
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Unexpected error updating configuration",
            error=str(e),
            user_id=user.get("id")
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )