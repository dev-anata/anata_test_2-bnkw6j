"""
FastAPI router implementation for data object management endpoints.

This module implements the data management API endpoints specified in the technical
specifications, providing secure access to data objects with streaming support,
authentication, and comprehensive error handling.

Version: 1.0.0
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from core.schemas import DataObjectSchema
from services.data_service import DataService
from api.dependencies import get_current_user, verify_admin_role
from core.exceptions import StorageException, ValidationException

# Configure router
router = APIRouter(prefix="/api/v1/data", tags=["Data"])

# Constants
CHUNK_SIZE = 8192  # 8KB chunks for streaming
MAX_UPLOAD_SIZE = 1024 * 1024 * 100  # 100MB max upload size

# Configure logger
logger = logging.getLogger(__name__)

@router.post("/", response_model=DataObjectSchema)
async def upload_data(
    file: UploadFile = File(...),
    execution_id: UUID,
    metadata: Dict[str, Any],
    data_service: DataService = Depends(),
    current_user: dict = Depends(get_current_user)
) -> DataObjectSchema:
    """
    Upload data file with metadata and validation.

    Args:
        file: File to upload
        execution_id: ID of the associated execution
        metadata: Additional metadata for the data object
        data_service: Injected data service
        current_user: Authenticated user details

    Returns:
        DataObjectSchema: Created data object details

    Raises:
        HTTPException: If upload fails or validation errors occur
    """
    try:
        # Validate file size
        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationException(
                "File too large",
                {"max_size": MAX_UPLOAD_SIZE, "actual_size": file.size}
            )

        # Add metadata
        metadata.update({
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file.size,
            "uploaded_by": current_user["id"]
        })

        # Store data with streaming
        data_object = await data_service.store_data(
            data=file.file,
            execution_id=execution_id,
            metadata=metadata
        )

        logger.info(
            "Data upload successful",
            extra={
                "object_id": str(data_object.id),
                "execution_id": str(execution_id),
                "user_id": current_user["id"]
            }
        )

        return data_object

    except ValidationException as e:
        logger.warning("Upload validation failed", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except StorageException as e:
        logger.error("Storage error during upload", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Storage operation failed")
    except Exception as e:
        logger.error("Unexpected error during upload", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{object_id}")
async def get_data_object(
    object_id: UUID,
    data_service: DataService = Depends(),
    current_user: dict = Depends(get_current_user)
) -> StreamingResponse:
    """
    Retrieve data object by ID with streaming support.

    Args:
        object_id: ID of data object to retrieve
        data_service: Injected data service
        current_user: Authenticated user details

    Returns:
        StreamingResponse: Streamed data object content

    Raises:
        HTTPException: If retrieval fails or object not found
    """
    try:
        # Get data object metadata first
        data_object = await data_service.get_data(object_id)
        if not data_object:
            raise ValidationException(
                "Data object not found",
                {"object_id": str(object_id)}
            )

        # Set up streaming response
        async def data_stream():
            async with data_service.get_data(object_id) as stream:
                while chunk := await stream.read(CHUNK_SIZE):
                    yield chunk

        # Log access
        logger.info(
            "Data object accessed",
            extra={
                "object_id": str(object_id),
                "user_id": current_user["id"]
            }
        )

        return StreamingResponse(
            data_stream(),
            media_type=data_object.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{data_object.metadata.get("filename", "data")}"'
            }
        )

    except ValidationException as e:
        logger.warning("Data retrieval validation failed", extra={"error": str(e)})
        raise HTTPException(status_code=404, detail=str(e))
    except StorageException as e:
        logger.error("Storage error during retrieval", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Storage operation failed")
    except Exception as e:
        logger.error("Unexpected error during retrieval", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/execution/{execution_id}")
async def list_execution_data(
    execution_id: UUID,
    page_size: int = 50,
    cursor: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    data_service: DataService = Depends(),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List data objects for an execution with pagination.

    Args:
        execution_id: ID of execution to list data for
        page_size: Number of items per page
        cursor: Pagination cursor
        filters: Optional additional filters
        data_service: Injected data service
        current_user: Authenticated user details

    Returns:
        Dict containing paginated list of data objects

    Raises:
        HTTPException: If listing fails
    """
    try:
        # Validate page size
        if not 1 <= page_size <= 100:
            raise ValidationException(
                "Invalid page size",
                {"min": 1, "max": 100, "actual": page_size}
            )

        # Get data objects
        data_objects = await data_service.list_execution_data(
            execution_id=execution_id,
            filters=filters
        )

        # Handle pagination
        start_idx = int(cursor) if cursor else 0
        end_idx = start_idx + page_size
        paginated_objects = data_objects[start_idx:end_idx]
        
        # Generate next cursor
        next_cursor = str(end_idx) if end_idx < len(data_objects) else None

        logger.info(
            "Listed execution data objects",
            extra={
                "execution_id": str(execution_id),
                "user_id": current_user["id"],
                "count": len(paginated_objects)
            }
        )

        return {
            "items": paginated_objects,
            "next_cursor": next_cursor,
            "total_count": len(data_objects)
        }

    except ValidationException as e:
        logger.warning("List validation failed", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except StorageException as e:
        logger.error("Storage error during listing", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Storage operation failed")
    except Exception as e:
        logger.error("Unexpected error during listing", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{object_id}")
async def delete_data_object(
    object_id: UUID,
    data_service: DataService = Depends(),
    current_user: dict = Depends(verify_admin_role)
) -> Dict[str, Any]:
    """
    Delete data object by ID with admin verification.

    Args:
        object_id: ID of data object to delete
        data_service: Injected data service
        current_user: Authenticated admin user details

    Returns:
        Dict containing deletion status

    Raises:
        HTTPException: If deletion fails or unauthorized
    """
    try:
        # Verify object exists
        data_object = await data_service.get_data(object_id)
        if not data_object:
            raise ValidationException(
                "Data object not found",
                {"object_id": str(object_id)}
            )

        # Delete object
        deleted = await data_service.delete_data(object_id)

        logger.info(
            "Data object deleted",
            extra={
                "object_id": str(object_id),
                "user_id": current_user["id"]
            }
        )

        return {
            "success": deleted,
            "message": "Data object deleted successfully"
        }

    except ValidationException as e:
        logger.warning("Delete validation failed", extra={"error": str(e)})
        raise HTTPException(status_code=404, detail=str(e))
    except StorageException as e:
        logger.error("Storage error during deletion", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Storage operation failed")
    except Exception as e:
        logger.error("Unexpected error during deletion", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")