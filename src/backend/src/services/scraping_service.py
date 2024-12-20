"""
Enhanced scraping service implementation with comprehensive error handling,
performance optimization, and monitoring capabilities.

This module implements the service layer for web scraping functionality,
coordinating between task processing, storage, and monitoring components
with enterprise-grade features including:
- Async task processing with circuit breaker pattern
- Comprehensive error handling and recovery
- Performance monitoring and metrics
- Rate limiting and resource optimization
- Storage integration with validation

Version: 1.0.0
"""

import asyncio  # version: 3.11+
from typing import Dict, List, Optional, Any  # version: 3.11+
from circuitbreaker import circuit_breaker  # version: 1.4.0
from datetime import datetime, timedelta

from scraping.spiders.base import BaseSpider
from core.interfaces import TaskProcessor
from core.types import TaskType, TaskConfig, TaskResult, ProcessingError
from storage.cloud_storage import CloudStorageBackend
from monitoring.metrics import MetricsCollector
from monitoring.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# Constants for retry and concurrency
RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0
MAX_CONCURRENT_SPIDERS = 10

class ScrapingService(TaskProcessor):
    """
    Enhanced service class implementing scraping task processing and coordination
    with comprehensive monitoring, error handling, and performance optimizations.

    Features:
    - Async task processing with circuit breaker
    - Spider health monitoring and validation
    - Rate limiting and resource optimization
    - Comprehensive error handling
    - Performance metrics collection
    - Storage integration with validation
    """

    def __init__(
        self,
        storage_backend: CloudStorageBackend,
        metrics_collector: MetricsCollector
    ) -> None:
        """
        Initialize scraping service with enhanced configuration.

        Args:
            storage_backend: Cloud storage backend for data persistence
            metrics_collector: Metrics collection service

        Raises:
            ConfigurationException: If initialization fails
        """
        self._storage = storage_backend
        self._metrics = metrics_collector
        self._spiders: Dict[str, BaseSpider] = {}
        self._rate_limits: Dict[str, Dict] = {}
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_SPIDERS)
        self.processor_type: TaskType = 'scrape'

        # Validate storage backend health
        self._validate_storage()

        logger.info(
            "Initialized scraping service",
            extra={"max_concurrent": MAX_CONCURRENT_SPIDERS}
        )

    def _validate_storage(self) -> None:
        """
        Validate storage backend health and configuration.

        Raises:
            StorageException: If storage validation fails
        """
        try:
            self._storage.validate_storage()
        except Exception as e:
            logger.error(
                "Storage validation failed",
                exc=e,
                extra={"storage_type": type(self._storage).__name__}
            )
            raise

    async def register_spider(
        self,
        source_id: str,
        spider_class: BaseSpider
    ) -> None:
        """
        Register a spider class for a specific source with validation.

        Args:
            source_id: Unique identifier for the data source
            spider_class: Spider class implementation

        Raises:
            ValidationException: If spider validation fails
        """
        try:
            # Validate spider implementation
            if not issubclass(spider_class, BaseSpider):
                raise ValueError("Spider must inherit from BaseSpider")

            # Validate spider health check
            health_status = await spider_class.validate_health()
            if not health_status:
                raise ValueError("Spider health check failed")

            # Configure rate limits
            rate_limits = spider_class.get_rate_limits()
            self._rate_limits[source_id] = rate_limits

            # Register spider
            self._spiders[source_id] = spider_class

            logger.info(
                "Spider registered",
                extra={
                    "source_id": source_id,
                    "spider_class": spider_class.__name__,
                    "rate_limits": rate_limits
                }
            )

        except Exception as e:
            logger.error(
                "Spider registration failed",
                exc=e,
                extra={
                    "source_id": source_id,
                    "spider_class": spider_class.__name__
                }
            )
            raise

    async def get_spider(self, source_id: str) -> Optional[BaseSpider]:
        """
        Get spider instance for a specific source with health validation.

        Args:
            source_id: Source identifier

        Returns:
            Optional[BaseSpider]: Spider instance if found and healthy

        Raises:
            ValidationException: If spider validation fails
        """
        spider = self._spiders.get(source_id)
        if not spider:
            logger.warning(
                "Spider not found",
                extra={"source_id": source_id}
            )
            return None

        # Validate spider health
        try:
            health_status = await spider.validate_health()
            if not health_status:
                logger.error(
                    "Spider health check failed",
                    extra={"source_id": source_id}
                )
                return None

            # Check rate limits
            rate_limits = self._rate_limits.get(source_id, {})
            if not self._check_rate_limits(source_id, rate_limits):
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "source_id": source_id,
                        "rate_limits": rate_limits
                    }
                )
                return None

            return spider

        except Exception as e:
            logger.error(
                "Spider validation failed",
                exc=e,
                extra={"source_id": source_id}
            )
            return None

    def _check_rate_limits(
        self,
        source_id: str,
        rate_limits: Dict[str, Any]
    ) -> bool:
        """
        Check if source is within rate limits.

        Args:
            source_id: Source identifier
            rate_limits: Rate limit configuration

        Returns:
            bool: True if within limits, False otherwise
        """
        # Implement rate limiting logic here
        return True  # Placeholder

    @circuit_breaker(failure_threshold=5, recovery_timeout=60)
    async def process(self, task: TaskConfig) -> TaskResult:
        """
        Process a scraping task with enhanced error handling and monitoring.

        Args:
            task: Task configuration containing source and parameters

        Returns:
            TaskResult: Result of scraping operation

        Raises:
            ProcessingError: If task processing fails
        """
        start_time = datetime.utcnow()
        source_id = task.get('source')

        try:
            # Validate task configuration
            if not source_id:
                raise ValueError("Missing source identifier in task configuration")

            # Get spider instance
            spider = await self.get_spider(source_id)
            if not spider:
                raise ProcessingError(f"No valid spider found for source: {source_id}")

            # Acquire concurrency semaphore
            async with self._semaphore:
                # Start performance monitoring
                self._metrics.record_scraping_metrics(
                    'start',
                    {'source_id': source_id}
                )

                # Execute spider with timeout
                try:
                    result = await asyncio.wait_for(
                        spider.process(task),
                        timeout=300  # 5 minutes timeout
                    )
                except asyncio.TimeoutError:
                    raise ProcessingError("Spider execution timed out")

                # Store scraped data
                if result.get('data'):
                    storage_result = await self._storage.store_object(
                        result['data'],
                        {
                            'source_id': source_id,
                            'task_id': task.get('id'),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    result['storage_path'] = storage_result.storage_path

                # Record completion metrics
                duration = (datetime.utcnow() - start_time).total_seconds()
                self._metrics.record_scraping_metrics(
                    'complete',
                    {
                        'source_id': source_id,
                        'duration': duration,
                        'items_scraped': result.get('items_scraped', 0)
                    }
                )

                logger.info(
                    "Task processing completed",
                    extra={
                        'source_id': source_id,
                        'duration': duration,
                        'items_scraped': result.get('items_scraped', 0)
                    }
                )

                return result

        except Exception as e:
            # Record error metrics
            self._metrics.record_scraping_metrics(
                'error',
                {
                    'source_id': source_id,
                    'error_type': type(e).__name__
                }
            )

            logger.error(
                "Task processing failed",
                exc=e,
                extra={'source_id': source_id, 'task': task}
            )
            raise ProcessingError(f"Task processing failed: {str(e)}")

    async def validate_health(self) -> Dict[str, bool]:
        """
        Validate health status of all registered spiders.

        Returns:
            Dict[str, bool]: Health status for each spider
        """
        health_status = {}
        
        try:
            # Check spider health
            for source_id, spider in self._spiders.items():
                try:
                    status = await spider.validate_health()
                    health_status[source_id] = status
                except Exception as e:
                    logger.error(
                        "Spider health check failed",
                        exc=e,
                        extra={"source_id": source_id}
                    )
                    health_status[source_id] = False

            # Validate storage backend
            try:
                self._storage.validate_storage()
                health_status['storage'] = True
            except Exception as e:
                logger.error(
                    "Storage health check failed",
                    exc=e
                )
                health_status['storage'] = False

            return health_status

        except Exception as e:
            logger.error(
                "Health validation failed",
                exc=e
            )
            return {'status': False, 'error': str(e)}