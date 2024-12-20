"""
Integration tests for the web scraping functionality of the Data Processing Pipeline.

These tests validate the complete scraping workflow including:
- Spider initialization and configuration
- Task processing and execution
- Error handling and retry mechanisms
- Performance metrics collection
- Data storage integration

Version: 1.0.0
"""

import pytest  # version: 7.4+
import pytest_asyncio  # version: 0.21+
import aiohttp  # version: 3.8+
from typing import Dict, List, Optional, Any  # version: 3.11+
from datetime import datetime, timedelta
import asyncio

from scraping.spiders.base import BaseSpider
from services.scraping_service import ScrapingService
from scraping.settings import scraping_settings
from tests.utils.fixtures import create_test_task, create_test_execution
from monitoring.metrics import MetricsCollector
from storage.cloud_storage import CloudStorageBackend
from core.exceptions import ProcessingError, ValidationException

# Test constants
TEST_SOURCE_ID = "test-source"
TEST_URL = "https://test-source.example.com"
TEST_TIMEOUT = 30
TEST_RETRY_COUNT = 3

class TestSpider(BaseSpider):
    """
    Enhanced test spider implementation for integration testing.
    
    Features:
    - Performance metrics collection
    - Error simulation
    - Resource monitoring
    - Data validation
    """
    
    name = "test_spider"
    allowed_domains = [TEST_URL.split("//")[1]]
    start_urls = [TEST_URL]

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize test spider with monitoring capabilities."""
        super().__init__(config or {
            "source": TEST_URL,
            "allowed_domains": self.allowed_domains,
            "parameters": {
                "timeout": TEST_TIMEOUT,
                "retries": TEST_RETRY_COUNT
            }
        })
        
        # Initialize metrics collection
        self.performance_metrics = {
            "pages_processed": 0,
            "items_scraped": 0,
            "processing_time": 0.0,
            "error_count": 0
        }
        
        # Configure error simulation
        self.error_count = 0
        self.should_fail = config.get("simulate_errors", False) if config else False

    async def parse(self, response) -> List[Dict[str, Any]]:
        """
        Enhanced parse method with metrics collection and validation.
        
        Args:
            response: Scrapy response object
            
        Returns:
            List of parsed items
            
        Raises:
            ProcessingError: If parsing fails
        """
        start_time = datetime.utcnow()
        
        try:
            # Simulate error if configured
            if self.should_fail and self.error_count < TEST_RETRY_COUNT:
                self.error_count += 1
                raise ProcessingError("Simulated parsing error")
            
            # Process test data
            items = [{
                "url": response.url,
                "title": f"Test Item {i}",
                "timestamp": datetime.utcnow().isoformat(),
                "content": f"Test content {i}"
            } for i in range(5)]
            
            # Update metrics
            self.performance_metrics["pages_processed"] += 1
            self.performance_metrics["items_scraped"] += len(items)
            self.performance_metrics["processing_time"] += \
                (datetime.utcnow() - start_time).total_seconds()
            
            return items
            
        except Exception as e:
            self.performance_metrics["error_count"] += 1
            raise ProcessingError(f"Parse error: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get collected performance metrics."""
        return self.performance_metrics

@pytest.fixture
async def storage_backend():
    """Fixture providing configured storage backend."""
    return CloudStorageBackend(
        bucket_name="test-bucket",
        region="us-central1",
        enable_versioning=False
    )

@pytest.fixture
async def metrics_collector():
    """Fixture providing metrics collector."""
    return MetricsCollector({
        "enabled": True,
        "collection_interval": 1
    })

@pytest.fixture
async def scraping_service(storage_backend, metrics_collector):
    """Fixture providing configured scraping service."""
    service = ScrapingService(storage_backend, metrics_collector)
    await service.register_spider(TEST_SOURCE_ID, TestSpider)
    return service

@pytest.mark.asyncio
async def test_spider_initialization():
    """Test spider initialization and configuration validation."""
    # Create test configuration
    config = {
        "source": TEST_URL,
        "allowed_domains": [TEST_URL.split("//")[1]],
        "parameters": {
            "timeout": TEST_TIMEOUT,
            "retries": TEST_RETRY_COUNT
        }
    }
    
    # Initialize spider
    spider = TestSpider(config)
    
    # Verify configuration
    assert spider.name == "test_spider"
    assert TEST_URL.split("//")[1] in spider.allowed_domains
    assert spider.custom_settings["DOWNLOAD_TIMEOUT"] == TEST_TIMEOUT
    assert spider.custom_settings["RETRY_TIMES"] == TEST_RETRY_COUNT
    assert spider.custom_settings["USER_AGENT"] == scraping_settings.user_agent

@pytest.mark.asyncio
async def test_spider_process_execution(scraping_service):
    """Test complete spider task processing workflow."""
    # Create test task
    task = await create_test_task(
        task_type="scrape",
        config={
            "source": TEST_URL,
            "parameters": {
                "timeout": TEST_TIMEOUT,
                "retries": TEST_RETRY_COUNT
            }
        }
    )
    
    # Process task
    result = await scraping_service.process(task.configuration)
    
    # Verify results
    assert result["status"] == "completed"
    assert result.get("items_scraped", 0) > 0
    assert result.get("storage_path") is not None
    
    # Verify metrics
    spider = await scraping_service.get_spider(TEST_SOURCE_ID)
    metrics = spider.get_metrics()
    assert metrics["pages_processed"] > 0
    assert metrics["items_scraped"] > 0
    assert metrics["processing_time"] > 0
    assert metrics["error_count"] == 0

@pytest.mark.asyncio
async def test_spider_error_handling(scraping_service):
    """Test spider error handling and retry mechanism."""
    # Create task with error simulation
    task = await create_test_task(
        task_type="scrape",
        config={
            "source": TEST_URL,
            "simulate_errors": True,
            "parameters": {
                "timeout": TEST_TIMEOUT,
                "retries": TEST_RETRY_COUNT
            }
        }
    )
    
    # Process task and expect retries
    with pytest.raises(ProcessingError) as exc_info:
        await scraping_service.process(task.configuration)
    
    # Verify error handling
    spider = await scraping_service.get_spider(TEST_SOURCE_ID)
    metrics = spider.get_metrics()
    assert metrics["error_count"] > 0
    assert spider.error_count <= TEST_RETRY_COUNT
    assert "Parse error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_spider_performance_requirements():
    """Test spider performance against requirements."""
    # Initialize spider with performance monitoring
    spider = TestSpider({
        "source": TEST_URL,
        "parameters": {
            "timeout": TEST_TIMEOUT,
            "retries": TEST_RETRY_COUNT
        }
    })
    
    start_time = datetime.utcnow()
    
    # Process multiple pages
    tasks = []
    for _ in range(10):  # Simulate 10 concurrent requests
        task = asyncio.create_task(spider.parse(type("Response", (), {
            "url": TEST_URL,
            "status": 200
        })))
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    duration = (datetime.utcnow() - start_time).total_seconds()
    metrics = spider.get_metrics()
    
    # Verify performance metrics
    pages_per_minute = (metrics["pages_processed"] / duration) * 60
    assert pages_per_minute >= 100, "Failed to meet 100 pages/minute requirement"
    assert metrics["error_count"] == 0, "Unexpected errors during performance test"