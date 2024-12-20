"""
FastAPI router implementation for task management endpoints.

This module implements REST API routes for task creation, monitoring, and management
with comprehensive error handling, performance monitoring, and security controls.

Version: 1.0.0
"""

from typing import List, Optional, Dict, Any  # version: 3.11+
from uuid import UUID  # version: 3.11+
import structlog  # version: 23.1+
from fastapi import APIRouter, Depends, HTTPException, Response, status  # version: 0.100+
from pydantic import BaseModel, Field  # version: 2.0+

from services.task_service import TaskService
from api.dependencies import get_task_service, get_current_user, verify_admin_role
from core.types import TaskType, TaskStatus
from core.exceptions import ValidationException, TaskException

# Configure structured logger
logger = structlog.get_logger(__name__)

# Initialize router with prefix and tags
router = APIRouter(prefix="/tasks", tags=["tasks"])

# Request/Response Models
class TaskCreateSchema(BaseModel):
    """Schema for task creation requests."""
    type: TaskType = Field(..., description="Type of task (scrape or ocr)")
    configuration: Dict[str, Any] = Field(..., description="Task configuration parameters")
    scheduled_at: Optional[str] = Field(None, description="Optional scheduled execution time")

class TaskResponseSchema(BaseModel):
    """Schema for task responses with HATEOAS links."""
    id: UUID
    type: TaskType
    status: TaskStatus
    configuration: Dict[str, Any]
    created_at: str
    updated_at: Optional[str]
    scheduled_at: Optional[str]
    links: Dict[str, str]

class TaskListQuerySchema(BaseModel):
    """Schema for task listing query parameters."""
    type: Optional[TaskType] = None
    status: Optional[TaskStatus] = None
    limit: Optional[int] = Field(100, ge=1, le=1000)
    cursor: Optional[str] = None

@router.post(
    "/",
    response_model=TaskResponseSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Task created successfully"},
        400: {"description": "Invalid request parameters"},
        401: {"description": "Authentication failed"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
async def create_task(
    task_data: TaskCreateSchema,
    response: Response,
    task_service: TaskService = Depends(get_task_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> TaskResponseSchema:
    """
    Create a new data processing task.
    
    Args:
        task_data: Task creation parameters
        response: FastAPI response object for headers
        task_service: Injected task service
        current_user: Authenticated user context
        
    Returns:
        TaskResponseSchema: Created task details
        
    Raises:
        HTTPException: If task creation fails
    """
    try:
        # Log task creation request
        logger.info(
            "Creating task",
            task_type=task_data.type,
            user_id=current_user.get("id")
        )
        
        # Create task
        start_time = time.time()
        task_id = await task_service.create_task(
            task_type=task_data.type,
            config=task_data.configuration,
            scheduled_at=task_data.scheduled_at
        )
        
        # Get created task details
        task = await task_service.get_task_status(task_id)
        
        # Add performance headers
        processing_time = int((time.time() - start_time) * 1000)
        response.headers["X-Processing-Time"] = str(processing_time)
        
        # Generate HATEOAS links
        links = {
            "self": f"/tasks/{task_id}",
            "cancel": f"/tasks/{task_id}",
            "status": f"/tasks/{task_id}/status"
        }
        
        return TaskResponseSchema(
            id=task_id,
            type=task.type,
            status=task.status,
            configuration=task.configuration,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
            scheduled_at=task.scheduled_at.isoformat() if task.scheduled_at else None,
            links=links
        )
        
    except ValidationException as e:
        logger.warning("Task validation failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except TaskException as e:
        logger.error("Task creation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/{task_id}",
    response_model=TaskResponseSchema,
    responses={
        200: {"description": "Task details retrieved successfully"},
        404: {"description": "Task not found"},
        401: {"description": "Authentication failed"},
        500: {"description": "Internal server error"}
    }
)
async def get_task(
    task_id: UUID,
    response: Response,
    task_service: TaskService = Depends(get_task_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> TaskResponseSchema:
    """
    Get details of a specific task.
    
    Args:
        task_id: UUID of task to retrieve
        response: FastAPI response object for headers
        task_service: Injected task service
        current_user: Authenticated user context
        
    Returns:
        TaskResponseSchema: Task details
        
    Raises:
        HTTPException: If task retrieval fails
    """
    try:
        # Log task retrieval request
        logger.info(
            "Retrieving task",
            task_id=str(task_id),
            user_id=current_user.get("id")
        )
        
        # Get task details
        start_time = time.time()
        task = await task_service.get_task_status(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        # Add performance headers
        processing_time = int((time.time() - start_time) * 1000)
        response.headers["X-Processing-Time"] = str(processing_time)
        
        # Generate HATEOAS links
        links = {
            "self": f"/tasks/{task_id}",
            "cancel": f"/tasks/{task_id}",
            "status": f"/tasks/{task_id}/status"
        }
        
        return TaskResponseSchema(
            id=task_id,
            type=task.type,
            status=task.status,
            configuration=task.configuration,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
            scheduled_at=task.scheduled_at.isoformat() if task.scheduled_at else None,
            links=links
        )
        
    except TaskException as e:
        logger.error("Task retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/",
    response_model=List[TaskResponseSchema],
    responses={
        200: {"description": "Tasks listed successfully"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Authentication failed"},
        500: {"description": "Internal server error"}
    }
)
async def list_tasks(
    query: TaskListQuerySchema = Depends(),
    response: Response = None,
    task_service: TaskService = Depends(get_task_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[TaskResponseSchema]:
    """
    List tasks with filtering and pagination.
    
    Args:
        query: Query parameters for filtering and pagination
        response: FastAPI response object for headers
        task_service: Injected task service
        current_user: Authenticated user context
        
    Returns:
        List[TaskResponseSchema]: List of tasks
        
    Raises:
        HTTPException: If task listing fails
    """
    try:
        # Log task list request
        logger.info(
            "Listing tasks",
            filters=query.dict(exclude_none=True),
            user_id=current_user.get("id")
        )
        
        # Get tasks with filtering
        start_time = time.time()
        tasks = await task_service.list_tasks(
            task_type=query.type,
            status=query.status,
            limit=query.limit,
            cursor=query.cursor
        )
        
        # Add performance headers
        processing_time = int((time.time() - start_time) * 1000)
        response.headers["X-Processing-Time"] = str(processing_time)
        
        # Add rate limit headers
        response.headers["X-Rate-Limit-Remaining"] = str(
            current_user.get("rate_limit", {}).get("remaining", 1000)
        )
        
        # Convert tasks to response schema
        return [
            TaskResponseSchema(
                id=task.id,
                type=task.type,
                status=task.status,
                configuration=task.configuration,
                created_at=task.created_at.isoformat(),
                updated_at=task.updated_at.isoformat() if task.updated_at else None,
                scheduled_at=task.scheduled_at.isoformat() if task.scheduled_at else None,
                links={
                    "self": f"/tasks/{task.id}",
                    "cancel": f"/tasks/{task.id}",
                    "status": f"/tasks/{task.id}/status"
                }
            )
            for task in tasks
        ]
        
    except ValidationException as e:
        logger.warning("Invalid task query parameters", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except TaskException as e:
        logger.error("Task listing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Task cancelled successfully"},
        401: {"description": "Authentication failed"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Task not found"},
        500: {"description": "Internal server error"}
    }
)
async def cancel_task(
    task_id: UUID,
    response: Response,
    task_service: TaskService = Depends(get_task_service),
    current_user: Dict[str, Any] = Depends(verify_admin_role)
) -> None:
    """
    Cancel a running or scheduled task (admin only).
    
    Args:
        task_id: UUID of task to cancel
        response: FastAPI response object for headers
        task_service: Injected task service
        current_user: Authenticated admin user context
        
    Raises:
        HTTPException: If task cancellation fails
    """
    try:
        # Log task cancellation request
        logger.info(
            "Cancelling task",
            task_id=str(task_id),
            user_id=current_user.get("id")
        )
        
        # Cancel task
        start_time = time.time()
        success = await task_service.cancel_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        # Add performance headers
        processing_time = int((time.time() - start_time) * 1000)
        response.headers["X-Processing-Time"] = str(processing_time)
        
        # Add audit log entry
        logger.info(
            "Task cancelled",
            task_id=str(task_id),
            user_id=current_user.get("id")
        )
        
    except TaskException as e:
        logger.error("Task cancellation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))