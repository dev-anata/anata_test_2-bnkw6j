"""
Health check endpoints for the Data Processing Pipeline API service.

This module implements comprehensive health check endpoints including:
- Basic liveness probe for kubernetes health checks
- Detailed readiness probe with component validation
- Graceful degradation support
- Performance monitoring
- Component status caching

Version: 1.0.0
"""

from typing import Dict, Any, Optional  # version: 3.11+
import asyncio  # version: 3.11+
from datetime import datetime
import time
from fastapi import APIRouter, Response, status  # version: 0.100+
from fastapi.responses import JSONResponse

from monitoring.metrics import track_request_duration
from monitoring.logger import Logger, get_logger

# Initialize router with prefix and tags
router = APIRouter(prefix="/health", tags=["Health"])

# Initialize logger
logger = get_logger(__name__)

# Component timeout configuration (in seconds)
COMPONENT_TIMEOUTS = {
    'database': 5.0,
    'storage': 3.0,
    'queue': 2.0
}

# Cache configuration
CACHE_TTL = 30  # seconds
_component_cache: Dict[str, Dict[str, Any]] = {}
_last_cache_time: float = 0

@router.get("/liveness")
@track_request_duration(method='GET', endpoint='/health/liveness')
async def get_liveness() -> Dict[str, Any]:
    """
    Basic health check endpoint for kubernetes liveness probe.
    
    Returns:
        Dict[str, Any]: Simple OK status response with timestamp
    """
    logger.info(
        "Liveness check requested",
        extra={"endpoint": "/health/liveness"}
    )
    
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "data_processing_pipeline"
    }

@router.get("/readiness")
@track_request_duration(method='GET', endpoint='/health/readiness')
async def get_readiness(response: Response) -> Dict[str, Any]:
    """
    Detailed health check endpoint for kubernetes readiness probe.
    Validates all system components with graceful degradation support.
    
    Args:
        response: FastAPI response object for status code

    Returns:
        Dict[str, Any]: Detailed system health status with component states
    """
    global _component_cache, _last_cache_time
    
    logger.info(
        "Readiness check requested",
        extra={"endpoint": "/health/readiness"}
    )

    # Check cache validity
    current_time = time.time()
    if current_time - _last_cache_time <= CACHE_TTL:
        cached_status = _component_cache
        if not cached_status.get('healthy', True):
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return cached_status

    # Initialize component checks
    components = ['database', 'storage', 'queue']
    check_tasks = [
        check_component_health(component, COMPONENT_TIMEOUTS[component])
        for component in components
    ]

    # Execute component checks concurrently
    try:
        component_results = await asyncio.gather(
            *check_tasks,
            return_exceptions=True
        )
    except Exception as e:
        logger.error(
            "Failed to execute component checks",
            exc=e,
            extra={"components": components}
        )
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "message": "Health check failed",
            "timestamp": datetime.utcnow().isoformat()
        }

    # Process component results
    component_statuses = {}
    all_healthy = True
    degraded = False

    for component, result in zip(components, component_results):
        if isinstance(result, Exception):
            logger.error(
                f"Component check failed: {component}",
                exc=result,
                extra={"component": component}
            )
            component_statuses[component] = {
                "status": "error",
                "error": str(result)
            }
            all_healthy = False
        else:
            component_statuses[component] = result
            if not result.get('healthy', False):
                all_healthy = False
            if result.get('degraded', False):
                degraded = True

    # Prepare response
    health_status = {
        "status": "ok" if all_healthy else "degraded" if degraded else "error",
        "timestamp": datetime.utcnow().isoformat(),
        "components": component_statuses,
        "healthy": all_healthy,
        "degraded": degraded
    }

    # Update cache
    _component_cache = health_status
    _last_cache_time = current_time

    # Set response status
    if not all_healthy and not degraded:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif degraded:
        response.status_code = status.HTTP_207_MULTI_STATUS

    return health_status

async def check_component_health(component: str, timeout: float) -> Dict[str, Any]:
    """
    Check health of an individual system component with timeout.
    
    Args:
        component: Name of component to check
        timeout: Maximum time to wait for check

    Returns:
        Dict[str, Any]: Component health status with metrics
    """
    start_time = time.time()
    
    try:
        async with asyncio.timeout(timeout):
            if component == 'database':
                # Check database connectivity
                # Placeholder for actual database check
                await asyncio.sleep(0.1)  # Simulated check
                return {
                    "healthy": True,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "connections": 5  # Example metric
                }
                
            elif component == 'storage':
                # Check storage service
                # Placeholder for actual storage check
                await asyncio.sleep(0.1)  # Simulated check
                return {
                    "healthy": True,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "available_gb": 1000  # Example metric
                }
                
            elif component == 'queue':
                # Check task queue
                # Placeholder for actual queue check
                await asyncio.sleep(0.1)  # Simulated check
                return {
                    "healthy": True,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "queue_depth": 10  # Example metric
                }
                
            else:
                raise ValueError(f"Unknown component: {component}")
                
    except asyncio.TimeoutError:
        logger.warning(
            f"Component check timed out: {component}",
            extra={
                "component": component,
                "timeout": timeout
            }
        )
        return {
            "healthy": False,
            "degraded": True,
            "error": "timeout",
            "latency_ms": (time.time() - start_time) * 1000
        }
        
    except Exception as e:
        logger.error(
            f"Component check failed: {component}",
            exc=e,
            extra={"component": component}
        )
        return {
            "healthy": False,
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000
        }