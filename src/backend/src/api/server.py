"""
Main FastAPI application server for the Data Processing Pipeline.

This module configures and initializes the API service with comprehensive security
controls, monitoring, and observability features. It implements a multi-layered
architecture with request processing, authentication, rate limiting, and error handling.

Version: 1.0.0
"""

import os  # version: 3.11+
import logging  # version: 3.11+
import uvicorn  # version: 0.22+
from typing import Dict, Any  # version: 3.11+
from fastapi import FastAPI, Request  # version: 0.100+
from fastapi.middleware.cors import CORSMiddleware  # version: 0.100+
from fastapi.openapi.utils import get_openapi

from api.routes import health as health_router
from api.routes import tasks as tasks_router
from api.middlewares import (
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    ErrorHandlerMiddleware
)
from api.auth import AuthMiddleware, get_current_user
from config.settings import settings
from monitoring.logger import get_logger
from monitoring.metrics import MetricsManager

# Initialize structured logger
logger = get_logger(__name__)

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application with comprehensive middleware stack.
    
    Returns:
        FastAPI: Configured application instance
    """
    # Initialize FastAPI with custom configuration
    app = FastAPI(
        title="Data Processing Pipeline API",
        description="Enterprise-grade API for data processing operations",
        version="1.0.0",
        docs_url="/api/docs" if not settings.env == "production" else None,
        redoc_url="/api/redoc" if not settings.env == "production" else None
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Trace-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
    )

    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Add comprehensive middleware stack
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    # Initialize metrics manager
    metrics_config = settings.get_monitoring_config()["metrics"]
    metrics_manager = MetricsManager(metrics_config)

    # Start metrics server if enabled
    if not settings.debug:
        metrics_manager.start_metrics_server(
            port=int(os.getenv("METRICS_PORT", 8000)),
            security_config={"local_only": True}
        )

    # Mount API routers
    app.include_router(
        health_router.router,
        prefix="/health",
        tags=["Health"]
    )
    app.include_router(
        tasks_router.router,
        prefix="/api/v1/tasks",
        tags=["Tasks"]
    )

    # Configure OpenAPI schema
    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="Data Processing Pipeline API",
            version="1.0.0",
            description="Enterprise-grade API for data processing operations",
            routes=app.routes
        )

        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer"
            }
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Configure shutdown handlers
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down API server")
        # Cleanup connections and resources
        await metrics_manager._client.close()

    logger.info(
        "API server initialized",
        extra={
            "environment": settings.env,
            "debug_mode": settings.debug
        }
    )

    return app

def main() -> None:
    """
    Entry point for running the API server.
    """
    # Configure logging
    log_config = settings.get_monitoring_config()["logging"]
    logging.basicConfig(
        level=log_config["level"],
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create application
    app = create_application()

    # Configure uvicorn server
    uvicorn_config = {
        "app": app,
        "host": "0.0.0.0",
        "port": int(os.getenv("PORT", 8080)),
        "workers": int(os.getenv("WORKERS", 4)),
        "log_config": None,  # Use our custom logging configuration
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        "timeout_keep_alive": 30,
        "access_log": False  # We handle request logging in middleware
    }

    # Add SSL configuration in production
    if settings.env == "production":
        uvicorn_config.update({
            "ssl_keyfile": os.getenv("SSL_KEYFILE"),
            "ssl_certfile": os.getenv("SSL_CERTFILE"),
            "ssl_ca_certs": os.getenv("SSL_CA_CERTS"),
            "ssl_ciphers": "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256"
        })

    # Start server
    logger.info(
        "Starting API server",
        extra={
            "host": uvicorn_config["host"],
            "port": uvicorn_config["port"],
            "workers": uvicorn_config["workers"]
        }
    )
    uvicorn.run(**uvicorn_config)

# Create application instance for ASGI servers
app = create_application()

if __name__ == "__main__":
    main()