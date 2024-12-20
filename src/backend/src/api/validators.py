"""
API request/response validation module implementing comprehensive validation logic for all API endpoints.

This module provides robust validation for API requests and responses using Pydantic schemas
and custom validators, ensuring data integrity and security across all API interactions.

Version: 1.0.0
"""

from datetime import datetime  # version: 3.11+
from typing import Dict, List, Optional, Any, Union  # version: 3.11+
from uuid import UUID  # version: 3.11+
from pydantic import BaseModel, Field, validator, root_validator  # version: 2.0+

from core.schemas import (
    TaskCreateSchema,
    TaskResponseSchema,
    TaskExecutionSchema,
    DataObjectSchema
)
from core.types import TaskType, TaskStatus
from core.exceptions import ValidationException
from ocr.validators import validate_ocr_task

# Mapping of endpoints to their request schemas
REQUEST_SCHEMAS = {
    "/tasks": TaskCreateSchema,
    "/tasks/{task_id}": TaskResponseSchema,
    "/executions": TaskExecutionSchema,
    "/data": DataObjectSchema
}

class APIRequestValidator:
    """
    Base validator class for API request validation with comprehensive error tracking.
    
    Attributes:
        validation_errors (Dict[str, Any]): Collection of validation errors
    """
    
    def __init__(self) -> None:
        """Initialize validator with empty error collection."""
        self.validation_errors: Dict[str, Any] = {}

    def validate_uuid(self, value: str) -> bool:
        """
        Validate string is a valid UUID.
        
        Args:
            value: String to validate as UUID
            
        Returns:
            bool: True if valid UUID format
        """
        try:
            UUID(value)
            return True
        except ValueError:
            return False

    def validate_datetime(self, value: str) -> bool:
        """
        Validate string is a valid ISO datetime.
        
        Args:
            value: String to validate as datetime
            
        Returns:
            bool: True if valid ISO datetime format
        """
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False

class TaskRequestValidator(APIRequestValidator):
    """
    Validator for task-related API requests with task-specific validation logic.
    
    Attributes:
        task_type (TaskType): Type of task being validated
        config (Dict[str, Any]): Task configuration to validate
    """
    
    def __init__(self, task_type: TaskType, config: Dict[str, Any]) -> None:
        """
        Initialize task validator with type and configuration.
        
        Args:
            task_type: Type of task to validate
            config: Task configuration dictionary
        """
        super().__init__()
        self.task_type = task_type
        self.config = config

    def validate_task_config(self) -> Dict[str, Any]:
        """
        Validate task configuration based on task type.
        
        Returns:
            Dict[str, Any]: Validated configuration dictionary
            
        Raises:
            ValidationException: If configuration is invalid
        """
        if not isinstance(self.config, dict):
            raise ValidationException(
                "Invalid configuration format",
                {"expected": "dict", "received": type(self.config).__name__}
            )

        # Validate common configuration fields
        if "source" not in self.config:
            raise ValidationException(
                "Missing required configuration field",
                {"field": "source"}
            )

        # Type-specific validation
        if self.task_type == "ocr":
            return validate_ocr_task(self.config)
        elif self.task_type == "scrape":
            return self._validate_scrape_config()
        else:
            raise ValidationException(
                "Unsupported task type",
                {"type": self.task_type}
            )

    def _validate_scrape_config(self) -> Dict[str, Any]:
        """
        Validate web scraping task configuration.
        
        Returns:
            Dict[str, Any]: Validated scraping configuration
            
        Raises:
            ValidationException: If scraping configuration is invalid
        """
        source = self.config.get("source")
        if not isinstance(source, str):
            raise ValidationException(
                "Invalid source URL",
                {"expected": "string URL", "received": type(source).__name__}
            )

        if not source.startswith(("http://", "https://")):
            raise ValidationException(
                "Invalid URL scheme",
                {"url": source, "supported_schemes": ["http", "https"]}
            )

        # Validate optional scraping parameters
        if "depth" in self.config:
            depth = self.config["depth"]
            if not isinstance(depth, int) or depth < 0:
                raise ValidationException(
                    "Invalid depth parameter",
                    {"depth": depth, "expected": "non-negative integer"}
                )

        if "rate_limit" in self.config:
            rate_limit = self.config["rate_limit"]
            if not isinstance(rate_limit, (int, float)) or rate_limit <= 0:
                raise ValidationException(
                    "Invalid rate limit",
                    {"rate_limit": rate_limit, "expected": "positive number"}
                )

        return self.config

def validate_request_payload(payload: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
    """
    Validate incoming API request payload against appropriate schema.
    
    Args:
        payload: Request payload to validate
        endpoint: API endpoint being called
        
    Returns:
        Dict[str, Any]: Validated request payload
        
    Raises:
        ValidationException: If payload validation fails
    """
    try:
        # Get appropriate schema for endpoint
        schema_class = REQUEST_SCHEMAS.get(endpoint)
        if not schema_class:
            raise ValidationException(
                "Unknown endpoint",
                {"endpoint": endpoint}
            )

        # For task creation, perform additional task-specific validation
        if endpoint == "/tasks" and "type" in payload:
            task_type = payload["type"]
            config = payload.get("configuration", {})
            
            validator = TaskRequestValidator(task_type, config)
            validated_config = validator.validate_task_config()
            payload["configuration"] = validated_config

        # Validate against schema
        validated = schema_class(**payload)
        return validated.dict(exclude_none=True)

    except Exception as e:
        raise ValidationException(
            "Request validation failed",
            {"error": str(e)}
        )

def validate_response_payload(payload: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
    """
    Validate outgoing API response payload against appropriate schema.
    
    Args:
        payload: Response payload to validate
        endpoint: API endpoint being called
        
    Returns:
        Dict[str, Any]: Validated response payload
        
    Raises:
        ValidationException: If response validation fails
    """
    try:
        # Get appropriate schema for endpoint
        schema_class = REQUEST_SCHEMAS.get(endpoint)
        if not schema_class:
            raise ValidationException(
                "Unknown endpoint",
                {"endpoint": endpoint}
            )

        # Validate against schema
        validated = schema_class(**payload)
        return validated.dict(
            exclude_none=True,
            by_alias=True
        )

    except Exception as e:
        raise ValidationException(
            "Response validation failed",
            {"error": str(e)}
        )

__all__ = [
    'validate_request_payload',
    'validate_response_payload',
    'TaskRequestValidator'
]