"""
FastAPI router implementation for OCR-related endpoints with enhanced security,
performance monitoring, and error handling.

This module implements the OCR API endpoints specified in the technical specifications
with comprehensive validation, monitoring, and security controls.

Version: 1.0.0
"""

from typing import Dict, Any, Optional, List  # version: 3.11+
import structlog  # version: 23.1+
from fastapi import APIRouter, Depends, HTTPException, Response, status  # version: 0.100+
from pydantic import BaseModel, validator  # version: 2.0+
from circuitbreaker import circuit_breaker  # version: 1.4+

from services.ocr_service import OCRService
from api.dependencies import get_current_user, get_task_service, get_storage_service
from core.exceptions import ValidationException, StorageException, TaskException

# Configure structured logger
logger = structlog.get_logger(__name__)

# Initialize router with prefix and tags
router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"])

# Constants for OCR operations
TASK_TIMEOUT = 300  # 5 minutes timeout
MAX_RETRIES = 3

class OCRTaskRequest(BaseModel):
    """
    Enhanced Pydantic model for OCR task request validation.
    
    Attributes:
        source_path: Path to source document for OCR
        extraction_type: Type of extraction (text, table, mixed)
        options: Optional processing configuration
        target_fields: Optional fields to extract
        enable_validation: Enable additional validation checks
    """
    source_path: str
    extraction_type: str
    options: Optional[Dict[str, Any]] = None
    target_fields: Optional[List[str]] = None
    enable_validation: Optional[bool] = True

    @validator("source_path")
    def validate_source_path(cls, value: str) -> str:
        """Validate source path format and accessibility."""
        if not value:
            raise ValueError("Source path cannot be empty")
            
        # Validate file extension
        valid_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]
        if not any(value.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(
                f"Invalid file format. Supported formats: {', '.join(valid_extensions)}"
            )
            
        return value

class OCRTaskResponse(BaseModel):
    """
    Enhanced Pydantic model for OCR task response.
    
    Attributes:
        task_id: Unique identifier for the OCR task
        status: Current task status
        result_path: Optional path to results in storage
        metadata: Optional processing metadata
        errors: Optional list of processing errors
    """
    task_id: str
    status: str
    result_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def create_ocr_task(
    request: OCRTaskRequest,
    task_service = Depends(get_task_service),
    current_user: dict = Depends(get_current_user)
) -> OCRTaskResponse:
    """
    Create a new OCR processing task with enhanced validation and monitoring.
    
    Args:
        request: Validated OCR task request
        task_service: Injected task service
        current_user: Authenticated user context
        
    Returns:
        OCRTaskResponse: Created task details
        
    Raises:
        HTTPException: If task creation fails
    """
    try:
        logger.info(
            "Creating OCR task",
            user_id=current_user.get("id"),
            source_path=request.source_path
        )
        
        # Create task configuration
        task_config = {
            "source_path": request.source_path,
            "extraction_type": request.extraction_type,
            "options": request.options or {},
            "target_fields": request.target_fields,
            "enable_validation": request.enable_validation,
            "user_id": current_user.get("id")
        }
        
        # Create task
        task_id = await task_service.create_task(
            task_type="ocr",
            config=task_config
        )
        
        logger.info(
            "Created OCR task",
            task_id=str(task_id),
            user_id=current_user.get("id")
        )
        
        return OCRTaskResponse(
            task_id=str(task_id),
            status="pending",
            metadata={
                "created_by": current_user.get("id"),
                "source_path": request.source_path,
                "extraction_type": request.extraction_type
            }
        )
        
    except ValidationException as e:
        logger.error(
            "OCR task validation failed",
            error=str(e),
            user_id=current_user.get("id")
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to create OCR task",
            error=str(e),
            user_id=current_user.get("id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create OCR task"
        )

@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    task_service = Depends(get_task_service),
    current_user: dict = Depends(get_current_user),
    response: Response = None
) -> OCRTaskResponse:
    """
    Get status of an OCR task with caching.
    
    Args:
        task_id: ID of task to check
        task_service: Injected task service
        current_user: Authenticated user context
        response: FastAPI response for setting cache headers
        
    Returns:
        OCRTaskResponse: Current task status and metadata
        
    Raises:
        HTTPException: If status check fails
    """
    try:
        logger.debug(
            "Checking OCR task status",
            task_id=task_id,
            user_id=current_user.get("id")
        )
        
        # Get task status
        task_status = await task_service.get_task_status(task_id)
        
        # Set cache control headers
        if task_status in ["completed", "failed"]:
            response.headers["Cache-Control"] = "public, max-age=3600"
        else:
            response.headers["Cache-Control"] = "no-cache"
            
        return OCRTaskResponse(
            task_id=task_id,
            status=task_status,
            metadata={
                "checked_by": current_user.get("id"),
                "checked_at": "utcnow"
            }
        )
        
    except ValidationException as e:
        logger.error(
            "Invalid task ID",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    except Exception as e:
        logger.error(
            "Failed to get task status",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task status"
        )

@router.get("/{task_id}/result")
@circuit_breaker(failure_threshold=3, recovery_timeout=30)
async def get_task_result(
    task_id: str,
    task_service = Depends(get_task_service),
    storage_service = Depends(get_storage_service),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get results of a completed OCR task with error handling.
    
    Args:
        task_id: ID of task to get results for
        task_service: Injected task service
        storage_service: Injected storage service
        current_user: Authenticated user context
        
    Returns:
        Dict containing OCR results and metadata
        
    Raises:
        HTTPException: If result retrieval fails
    """
    try:
        logger.info(
            "Retrieving OCR task results",
            task_id=task_id,
            user_id=current_user.get("id")
        )
        
        # Check task status
        task_status = await task_service.get_task_status(task_id)
        if task_status != "completed":
            raise ValidationException(
                "Task results not available",
                {"status": task_status}
            )
            
        # Get task result from storage
        async with storage_service.retrieve_data(task_id) as result_data:
            result = {
                "task_id": task_id,
                "status": "completed",
                "result": result_data,
                "metadata": {
                    "retrieved_by": current_user.get("id"),
                    "retrieved_at": "utcnow"
                }
            }
            
        logger.info(
            "Retrieved OCR task results",
            task_id=task_id,
            user_id=current_user.get("id")
        )
        
        return result
        
    except ValidationException as e:
        logger.error(
            "Invalid task state for results",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except StorageException as e:
        logger.error(
            "Failed to retrieve task results",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task results"
        )
    except Exception as e:
        logger.error(
            "Unexpected error retrieving results",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task results"
        )