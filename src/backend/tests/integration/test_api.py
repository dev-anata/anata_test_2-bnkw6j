"""
Integration tests for FastAPI application endpoints.

This module implements comprehensive integration tests for the API endpoints including:
- Authentication and authorization
- Rate limiting
- Error handling
- Data processing workflows
- Performance requirements validation

Version: 1.0.0
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import uuid4

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient  # version: 0.100+
import time_machine  # version: 2.9+

from api.server import app
from tests.utils.mocks import MockTaskService
from tests.utils.fixtures import create_test_task, create_test_execution
from core.exceptions import ValidationException, TaskException

# Configure structured logger
logger = structlog.get_logger(__name__)

# Test constants
TEST_API_KEY = "test-api-key-123"
TEST_RATE_LIMIT = 1000
TEST_RATE_LIMIT_WINDOW = 3600

# Test data
TEST_TASK_PAYLOAD = {
    "type": "scrape",
    "configuration": {
        "source_url": "https://test.example.com",
        "parameters": {
            "depth": 1,
            "timeout": 30
        }
    }
}

@pytest.mark.integration
class TestAPIIntegration:
    """Integration test suite for API endpoints."""

    def setup_method(self):
        """Setup method run before each test."""
        # Initialize test client
        self.client = TestClient(app)
        
        # Configure mock services
        self.task_service = MockTaskService()
        app.dependency_overrides = {
            "get_task_service": lambda: self.task_service
        }
        
        # Set test API key
        self.client.headers.update({"X-API-Key": TEST_API_KEY})
        
        logger.info("Test setup complete")

    def teardown_method(self):
        """Cleanup method run after each test."""
        # Reset dependency overrides
        app.dependency_overrides = {}
        
        # Clear test data
        self.task_service = None
        
        logger.info("Test cleanup complete")

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoints for liveness and readiness."""
        # Test liveness endpoint
        response = self.client.get("/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["service"] == "data_processing_pipeline"

        # Test readiness endpoint
        response = self.client.get("/health/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ok", "degraded"]
        assert "components" in data
        assert all(c in data["components"] for c in ["database", "storage", "queue"])

    @pytest.mark.asyncio
    async def test_create_task_success(self):
        """Test successful task creation with validation."""
        response = self.client.post("/api/v1/tasks", json=TEST_TASK_PAYLOAD)
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert "type" == TEST_TASK_PAYLOAD["type"]
        assert "status" == "pending"
        assert "links" in data
        assert all(link in data["links"] for link in ["self", "cancel", "status"])
        
        # Verify processing time header
        assert "X-Processing-Time" in response.headers
        processing_time = int(response.headers["X-Processing-Time"])
        assert processing_time < 500  # Verify performance requirement

    @pytest.mark.asyncio
    async def test_create_task_validation_error(self):
        """Test task creation with invalid payload."""
        invalid_payload = {
            "type": "invalid_type",
            "configuration": {}
        }
        
        response = self.client.post("/api/v1/tasks", json=invalid_payload)
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "validation_error"
        assert "message" in data
        assert "details" in data

    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test task status retrieval."""
        # Create test task
        task = await create_test_task()
        self.task_service._task_statuses[task.id] = "running"
        
        response = self.client.get(f"/api/v1/tasks/{task.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(task.id)
        assert data["status"] == "running"
        assert "links" in data

    @pytest.mark.asyncio
    async def test_list_tasks(self):
        """Test task listing with filters."""
        # Create test tasks
        tasks = [
            await create_test_task(task_type="scrape", status="completed"),
            await create_test_task(task_type="ocr", status="pending")
        ]
        for task in tasks:
            self.task_service._task_statuses[task.id] = task.status
        
        # Test without filters
        response = self.client.get("/api/v1/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Test with type filter
        response = self.client.get("/api/v1/tasks?type=scrape")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "scrape"
        
        # Test with status filter
        response = self.client.get("/api/v1/tasks?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test task cancellation with admin role."""
        # Create test task
        task = await create_test_task(status="running")
        self.task_service._task_statuses[task.id] = "running"
        
        # Set admin role header
        self.client.headers.update({"X-Role": "admin"})
        
        response = self.client.delete(f"/api/v1/tasks/{task.id}")
        assert response.status_code == 204
        
        # Verify task was cancelled
        status = await self.task_service.get_task_status(task.id)
        assert status == "cancelled"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Configure rate limit of 5 requests per minute for testing
        app.state.rate_limit = 5
        app.state.rate_limit_window = 60
        
        # Send requests up to limit
        for _ in range(5):
            response = self.client.get("/health/liveness")
            assert response.status_code == 200
            assert "X-RateLimit-Remaining" in response.headers
        
        # Verify rate limit exceeded
        response = self.client.get("/health/liveness")
        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "rate_limit_exceeded"
        assert "retry_after" in data
        
        # Verify retry-after header
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test comprehensive error handling."""
        # Test validation error
        self.task_service._error_triggers["validation"] = ValidationException(
            "Invalid configuration",
            {"field": "source_url"}
        )
        response = self.client.post("/api/v1/tasks", json=TEST_TASK_PAYLOAD)
        assert response.status_code == 400
        
        # Test task error
        self.task_service._error_triggers["task"] = TaskException(
            "Processing failed",
            "task-123",
            {"reason": "timeout"}
        )
        response = self.client.get("/api/v1/tasks/task-123")
        assert response.status_code == 500
        
        # Test unauthorized access
        self.client.headers.pop("X-API-Key")
        response = self.client.get("/api/v1/tasks")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_performance_requirements(self):
        """Test API performance requirements."""
        # Test API latency requirement (<500ms p95)
        latencies = []
        for _ in range(100):
            start_time = time.time()
            response = self.client.get("/health/liveness")
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            assert response.status_code == 200
        
        p95_latency = sorted(latencies)[95]
        assert p95_latency < 500
        
        # Test task processing time (<5min per task)
        start_time = time.time()
        response = self.client.post("/api/v1/tasks", json=TEST_TASK_PAYLOAD)
        processing_time = time.time() - start_time
        assert processing_time < 300  # 5 minutes
        assert response.status_code == 201