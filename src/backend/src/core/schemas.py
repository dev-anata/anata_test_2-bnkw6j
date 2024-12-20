"""
Pydantic schema definitions for data validation and serialization across the data processing pipeline.

This module provides comprehensive schema validation for requests, responses, and data transfer objects
using Pydantic models with strict validation rules and detailed error messages.

Version: 1.0.0
"""

from datetime import datetime  # version: 3.11+
from typing import Dict, List, Optional, Any, Union  # version: 3.11+
from uuid import UUID, uuid4  # version: 3.11+

from pydantic import BaseModel, Field, validator, root_validator  # version: 2.0+

from core.types import (
    TaskType, TaskStatus, TaskConfig, TaskResult, TaskID,
    ExecutionID, DataObjectID, Metadata
)
from core.models import Task, TaskExecution, DataObject


class TaskCreateSchema(BaseModel):
    """
    Schema for validating task creation requests with comprehensive validation rules.
    
    Attributes:
        type (TaskType): Type of task (scrape or ocr)
        configuration (Dict[str, Any]): Task-specific configuration
        scheduled_at (Optional[datetime]): When to schedule the task
        description (Optional[str]): Human-readable task description
        tags (Optional[Dict[str, str]]): Key-value pairs for task categorization
    """
    type: TaskType = Field(..., description="Type of task (scrape or ocr)")
    configuration: Dict[str, Any] = Field(
        ...,
        description="Task-specific configuration parameters"
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Optional timestamp for scheduled execution"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional task description"
    )
    tags: Optional[Dict[str, str]] = Field(
        None,
        max_length=10,
        description="Optional key-value pairs for categorization"
    )

    @validator("configuration")
    def validate_configuration(cls, value: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate task configuration based on task type."""
        task_type = values.get("type")
        
        if not isinstance(value, dict):
            raise ValueError("Configuration must be a dictionary")
            
        if "source" not in value:
            raise ValueError("Configuration must include 'source' field")
            
        # Validate scraping task configuration
        if task_type == "scrape":
            if not isinstance(value.get("source"), str):
                raise ValueError("Scraping source must be a string URL")
            if not value["source"].startswith(("http://", "https://")):
                raise ValueError("Scraping source must be a valid HTTP(S) URL")
                
        # Validate OCR task configuration
        elif task_type == "ocr":
            if not isinstance(value.get("source"), str):
                raise ValueError("OCR source must be a string path")
            if not value["source"].endswith((".pdf", ".png", ".jpg", ".jpeg")):
                raise ValueError("OCR source must be a PDF or image file")
                
        return value

    @validator("tags")
    def validate_tags(cls, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Validate task tags format and content."""
        if value is not None:
            if len(value) > 10:
                raise ValueError("Maximum 10 tags allowed")
            
            for key, val in value.items():
                if not isinstance(key, str) or not isinstance(val, str):
                    raise ValueError("Tags must be string key-value pairs")
                if len(key) > 50 or len(val) > 100:
                    raise ValueError("Tag keys limited to 50 chars, values to 100 chars")
                
        return value


class TaskResponseSchema(BaseModel):
    """
    Schema for task response serialization with complete task information.
    
    Attributes:
        id (UUID): Unique task identifier
        type (TaskType): Type of task
        status (TaskStatus): Current task status
        configuration (Dict[str, Any]): Task configuration
        created_at (datetime): Task creation timestamp
        updated_at (Optional[datetime]): Last update timestamp
        execution_history (Optional[List[UUID]]): List of execution IDs
        tags (Optional[Dict[str, str]]): Task tags
        metadata (Optional[Dict[str, Any]]): Additional task metadata
    """
    id: UUID = Field(..., description="Unique task identifier")
    type: TaskType = Field(..., description="Type of task")
    status: TaskStatus = Field(..., description="Current task status")
    configuration: Dict[str, Any] = Field(..., description="Task configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    execution_history: Optional[List[UUID]] = Field(
        default_factory=list,
        description="List of execution attempt IDs"
    )
    tags: Optional[Dict[str, str]] = Field(None, description="Task categorization tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class TaskExecutionSchema(BaseModel):
    """
    Schema for task execution data with detailed execution tracking.
    
    Attributes:
        id (UUID): Unique execution identifier
        task_id (UUID): Associated task ID
        status (TaskStatus): Execution status
        start_time (datetime): Execution start time
        end_time (Optional[datetime]): Execution end time
        result (Optional[Dict[str, Any]]): Execution results
        error_message (Optional[str]): Error details if failed
        performance_metrics (Optional[Dict[str, Any]]): Execution metrics
        logs (Optional[List[str]]): Execution log entries
    """
    id: UUID = Field(..., description="Unique execution identifier")
    task_id: UUID = Field(..., description="Associated task ID")
    status: TaskStatus = Field(..., description="Execution status")
    start_time: datetime = Field(..., description="Start timestamp")
    end_time: Optional[datetime] = Field(None, description="End timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution results")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    performance_metrics: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution performance metrics"
    )
    logs: Optional[List[str]] = Field(
        default_factory=list,
        description="Execution log entries"
    )

    @root_validator
    def validate_execution_state(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate execution state consistency."""
        status = values.get("status")
        end_time = values.get("end_time")
        result = values.get("result")
        error_message = values.get("error_message")

        if status == "completed":
            if not end_time:
                raise ValueError("Completed execution must have end_time")
            if not result:
                raise ValueError("Completed execution must have results")
            if error_message:
                raise ValueError("Completed execution cannot have error_message")
                
        elif status == "failed":
            if not end_time:
                raise ValueError("Failed execution must have end_time")
            if not error_message:
                raise ValueError("Failed execution must have error_message")
            if result:
                raise ValueError("Failed execution cannot have results")
                
        return values


class DataObjectSchema(BaseModel):
    """
    Schema for data object validation and serialization with storage validation.
    
    Attributes:
        id (UUID): Unique object identifier
        execution_id (UUID): Associated execution ID
        storage_path (str): GCS storage path
        content_type (str): MIME type of stored data
        metadata (Dict[str, Any]): Object metadata
        created_at (datetime): Creation timestamp
        size_bytes (Optional[int]): Object size in bytes
        checksum (Optional[str]): Object content checksum
    """
    id: UUID = Field(..., description="Unique object identifier")
    execution_id: UUID = Field(..., description="Associated execution ID")
    storage_path: str = Field(..., description="GCS storage path")
    content_type: str = Field(..., description="Content MIME type")
    metadata: Dict[str, Any] = Field(..., description="Object metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    size_bytes: Optional[int] = Field(None, gt=0, description="Object size in bytes")
    checksum: Optional[str] = Field(None, description="Content checksum")

    @validator("storage_path")
    def validate_storage_path(cls, value: str) -> str:
        """Validate GCS storage path format."""
        if not value.startswith("gs://"):
            raise ValueError("Storage path must start with 'gs://'")
            
        parts = value.replace("gs://", "").split("/")
        if len(parts) < 2:
            raise ValueError("Storage path must include bucket and object path")
            
        bucket = parts[0]
        if not (3 <= len(bucket) <= 63):
            raise ValueError("Invalid bucket name length")
        if not bucket.islower():
            raise ValueError("Bucket name must be lowercase")
            
        return value

    @validator("content_type")
    def validate_content_type(cls, value: str) -> str:
        """Validate content type format."""
        if "/" not in value:
            raise ValueError("Invalid content type format")
        if not value.strip():
            raise ValueError("Content type cannot be empty")
        return value


__all__ = [
    'TaskCreateSchema',
    'TaskResponseSchema',
    'TaskExecutionSchema',
    'DataObjectSchema'
]