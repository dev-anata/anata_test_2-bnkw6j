"""
FastAPI router implementation for web scraping endpoints with comprehensive validation,
error handling, and security controls.

This module implements the RESTful API endpoints for web scraping task management
as specified in the technical specifications, with features including:
- Task creation and monitoring
- Rate limiting and security controls
- Performance optimization
- Comprehensive error handling
- Request/response validation

Version: 1.0.0
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from services.task_service import TaskService
from services.scraping_service import ScrapingService
from core.schemas import TaskCreateSchema, TaskResponseSchema, TaskListResponseSchema
from api.dependencies import get_task_service, get_current_user, validate_rate_limit
from core.exceptions import ValidationException, TaskException, StorageException
from monitoring.metrics import track_request_duration
from monitoring.logger import get_logger

# Initialize structured logger
logger = get_logger(__name__)

# Initialize router with prefix and tags
router = APIRouter(
    prefix="/api/v1/scraping",
    tags=["scraping"]
)

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskResponseSchema
)
@track_request_duration(method="POST", endpoint="/scraping")
async def create_scraping_task(
    request: Request,
    response: Response,
    task_data: TaskCreateSchema,
    task_service: TaskService = Depends(get_task_service),
    current_user: dict = Depends(get_current_user),
    rate_limit: None = Depends(validate_rate_limit)
) -> TaskResponseSchema:
    """
    Create a new web scraping task with comprehensive validation.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        task_data: Validated task creation data
        task_service: Injected task service
        current_user: Validated user context
        rate_limit: Rate limit validation dependency

    Returns:
        TaskResponseSchema: Created task details

    Raises:
        HTTPException: If task creation fails or validation errors occur
    """
    try:
        # Validate task type
        if task_data.type != "scrape":
            raise ValidationException(
                "Invalid task type",
                {"type": task_data.type, "expected": "scrape"}
            )

        # Validate scraping configuration
        if "source" not in task_data.configuration:
            raise ValidationException(
                "Missing source URL in configuration",
                {"configuration": task_data.configuration}
            )

        # Create task with user context
        task_id = await task_service.create_task(
            task_type="scrape",
            config={
                **task_data.configuration,
                "created_by": current_user["client_id"]
            },
            scheduled_at=task_data.scheduled_at
        )

        # Get created task details
        task = await task_service.get_task_status(task_id)

        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(
            current_user.get("rate_limit", 1000)
        )

        logger.info(
            "Created scraping task",
            extra={
                "task_id": str(task_id),
                "user_id": current_user["client_id"]
            }
        )

        return TaskResponseSchema(
            id=task_id,
            type="scrape",
            status=task.status,
            configuration=task_data.configuration,
            created_at=task.created_at,
            updated_at=task.updated_at,
            scheduled_at=task_data.scheduled_at,
            tags=task_data.tags
        )

    except ValidationException as e:
        logger.warning(
            "Validation error creating scraping task",
            exc=e,
            extra={"user_id": current_user["client_id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "details": e.details}
        )
    except TaskException as e:
        logger.error(
            "Error creating scraping task",
            exc=e,
            extra={"user_id": current_user["client_id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "task_creation_failed", "details": str(e)}
        )
    except Exception as e:
        logger.error(
            "Unexpected error creating scraping task",
            exc=e,
            extra={"user_id": current_user["client_id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error"}
        )

@router.get(
    "/{task_id}",
    response_model=TaskResponseSchema
)
@track_request_duration(method="GET", endpoint="/scraping/{task_id}")
async def get_scraping_task(
    request: Request,
    task_id: UUID,
    task_service: TaskService = Depends(get_task_service),
    current_user: dict = Depends(get_current_user)
) -> TaskResponseSchema:
    """
    Get status and details of a scraping task.

    Args:
        request: FastAPI request object
        task_id: UUID of task to retrieve
        task_service: Injected task service
        current_user: Validated user context

    Returns:
        TaskResponseSchema: Task details and status

    Raises:
        HTTPException: If task not found or access denied
    """
    try:
        # Get task details
        task = await task_service.get_task_status(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "task_not_found", "task_id": str(task_id)}
            )

        # Verify task ownership
        if task.configuration.get("created_by") != current_user["client_id"]:
            logger.warning(
                "Unauthorized task access attempt",
                extra={
                    "task_id": str(task_id),
                    "user_id": current_user["client_id"]
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "access_denied"}
            )

        logger.info(
            "Retrieved scraping task",
            extra={
                "task_id": str(task_id),
                "user_id": current_user["client_id"]
            }
        )

        return TaskResponseSchema(
            id=task_id,
            type="scrape",
            status=task.status,
            configuration=task.configuration,
            created_at=task.created_at,
            updated_at=task.updated_at,
            execution_history=task.execution_history
        )

    except HTTPException:
        raise
    except TaskException as e:
        logger.error(
            "Error retrieving scraping task",
            exc=e,
            extra={
                "task_id": str(task_id),
                "user_id": current_user["client_id"]
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "task_retrieval_failed", "details": str(e)}
        )
    except Exception as e:
        logger.error(
            "Unexpected error retrieving scraping task",
            exc=e,
            extra={
                "task_id": str(task_id),
                "user_id": current_user["client_id"]
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error"}
        )

@router.get(
    "/",
    response_model=TaskListResponseSchema
)
@track_request_duration(method="GET", endpoint="/scraping")
async def list_scraping_tasks(
    request: Request,
    response: Response,
    task_service: TaskService = Depends(get_task_service),
    current_user: dict = Depends(get_current_user),
    page: Optional[int] = 1,
    page_size: Optional[int] = 50,
    status: Optional[str] = None
) -> TaskListResponseSchema:
    """
    List scraping tasks with filtering and pagination.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        task_service: Injected task service
        current_user: Validated user context
        page: Page number (default: 1)
        page_size: Items per page (default: 50)
        status: Optional status filter

    Returns:
        TaskListResponseSchema: Paginated list of tasks

    Raises:
        HTTPException: If listing fails or validation errors occur
    """
    try:
        # Validate pagination parameters
        if page < 1:
            raise ValidationException(
                "Invalid page number",
                {"page": page, "min_value": 1}
            )
        if page_size < 1 or page_size > 100:
            raise ValidationException(
                "Invalid page size",
                {"page_size": page_size, "min_value": 1, "max_value": 100}
            )

        # List tasks with filters
        tasks = await task_service.list_tasks(
            task_type="scrape",
            status=status,
            created_by=current_user["client_id"],
            page=page,
            page_size=page_size
        )

        # Add pagination headers
        response.headers["X-Total-Count"] = str(len(tasks))
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(page_size)

        logger.info(
            "Listed scraping tasks",
            extra={
                "user_id": current_user["client_id"],
                "page": page,
                "page_size": page_size,
                "status_filter": status
            }
        )

        return TaskListResponseSchema(
            items=[
                TaskResponseSchema(
                    id=task.id,
                    type="scrape",
                    status=task.status,
                    configuration=task.configuration,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    execution_history=task.execution_history
                )
                for task in tasks
            ],
            page=page,
            page_size=page_size,
            total=len(tasks)
        )

    except ValidationException as e:
        logger.warning(
            "Validation error listing scraping tasks",
            exc=e,
            extra={"user_id": current_user["client_id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "details": e.details}
        )
    except TaskException as e:
        logger.error(
            "Error listing scraping tasks",
            exc=e,
            extra={"user_id": current_user["client_id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "task_listing_failed", "details": str(e)}
        )
    except Exception as e:
        logger.error(
            "Unexpected error listing scraping tasks",
            exc=e,
            extra={"user_id": current_user["client_id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error"}
        )