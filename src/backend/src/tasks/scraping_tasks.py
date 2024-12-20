"""
Enterprise-grade web scraping task management implementation with advanced features.

This module implements specialized task handling for web scraping operations with:
- Advanced rate limiting and throttling
- Comprehensive error handling and recovery
- Performance optimization and monitoring
- Security controls and pattern detection
- Resource management and cleanup

Version: 1.0.0
"""

from typing import Dict, List, Optional, Any  # version: 3.11+
import jsonschema  # version: 4.17+
from tenacity import (  # version: 8.2+
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from ratelimit import limits, RateLimitException  # version: 2.2+

from tasks.base import BaseTask, BaseTaskExecutor
from scraping.spiders.base import BaseSpider
from core.types import TaskType, TaskConfig, TaskResult
from core.exceptions import (
    ValidationException, TaskException, ConfigurationException
)
from monitoring.metrics import MetricsCollector
from monitoring.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# Task configuration schema
SCRAPING_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "source": {"type": "string", "format": "uri"},
        "allowed_domains": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "rate_limit": {
            "type": "object",
            "properties": {
                "requests_per_second": {"type": "number", "minimum": 0.1},
                "burst_size": {"type": "integer", "minimum": 1}
            },
            "required": ["requests_per_second"]
        },
        "security": {
            "type": "object",
            "properties": {
                "verify_ssl": {"type": "boolean"},
                "respect_robots": {"type": "boolean"},
                "allowed_patterns": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "performance": {
            "type": "object",
            "properties": {
                "concurrent_requests": {"type": "integer", "minimum": 1},
                "timeout_seconds": {"type": "integer", "minimum": 1}
            }
        }
    },
    "required": ["source", "allowed_domains"]
}

class ScrapingTask(BaseTask):
    """
    Specialized task implementation for web scraping operations with advanced features.
    
    Features:
    - Comprehensive configuration validation
    - Spider registration and management
    - Rate limiting and throttling
    - Security pattern monitoring
    - Performance optimization
    """

    def __init__(self, metrics_collector: MetricsCollector) -> None:
        """
        Initialize scraping task handler with required components.

        Args:
            metrics_collector: Metrics collection service
        """
        super().__init__()
        self._metrics_collector = metrics_collector
        self._spiders: Dict[str, BaseSpider] = {}
        self._security_patterns: Dict[str, Any] = {}
        
        # Initialize task type
        self._task_type: TaskType = "scrape"
        
        logger.info(
            "Initialized scraping task handler",
            extra={"task_type": self._task_type}
        )

    @property
    def task_type(self) -> TaskType:
        """Get the task type."""
        return self._task_type

    async def validate_config(self, config: TaskConfig) -> bool:
        """
        Validate scraping task configuration with enhanced security checks.

        Args:
            config: Task configuration to validate

        Returns:
            bool: True if configuration is valid

        Raises:
            ValidationException: If configuration is invalid
        """
        try:
            # Validate against schema
            jsonschema.validate(config, SCRAPING_TASK_SCHEMA)
            
            # Security validations
            if not self._validate_security_settings(config):
                raise ValidationException(
                    "Security validation failed",
                    {"config": config}
                )
            
            # Rate limit validations
            if not self._validate_rate_limits(config):
                raise ValidationException(
                    "Rate limit validation failed",
                    {"config": config}
                )
            
            # Performance validations
            if not self._validate_performance_settings(config):
                raise ValidationException(
                    "Performance validation failed",
                    {"config": config}
                )
            
            logger.info(
                "Task configuration validated",
                extra={"config": config}
            )
            return True
            
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationException(
                "Invalid task configuration",
                {"error": str(e), "config": config}
            )
        except Exception as e:
            logger.error(
                "Configuration validation failed",
                exc=e,
                extra={"config": config}
            )
            raise

    def _validate_security_settings(self, config: TaskConfig) -> bool:
        """
        Validate security-related configuration settings.

        Args:
            config: Task configuration

        Returns:
            bool: True if security settings are valid
        """
        security = config.get("security", {})
        
        # Validate SSL settings
        if security.get("verify_ssl", True) is False:
            logger.warning(
                "SSL verification disabled",
                extra={"source": config["source"]}
            )
        
        # Validate allowed patterns
        allowed_patterns = security.get("allowed_patterns", [])
        if allowed_patterns:
            try:
                import re
                for pattern in allowed_patterns:
                    re.compile(pattern)
            except re.error:
                return False
        
        return True

    def _validate_rate_limits(self, config: TaskConfig) -> bool:
        """
        Validate rate limiting configuration.

        Args:
            config: Task configuration

        Returns:
            bool: True if rate limits are valid
        """
        rate_limit = config.get("rate_limit", {})
        
        # Validate rate limit settings
        if "requests_per_second" in rate_limit:
            rps = rate_limit["requests_per_second"]
            if rps <= 0 or rps > 100:  # Maximum 100 requests per second
                return False
        
        return True

    def _validate_performance_settings(self, config: TaskConfig) -> bool:
        """
        Validate performance-related configuration.

        Args:
            config: Task configuration

        Returns:
            bool: True if performance settings are valid
        """
        performance = config.get("performance", {})
        
        # Validate concurrent requests
        if "concurrent_requests" in performance:
            concurrent = performance["concurrent_requests"]
            if concurrent <= 0 or concurrent > 32:  # Maximum 32 concurrent requests
                return False
        
        # Validate timeout
        if "timeout_seconds" in performance:
            timeout = performance["timeout_seconds"]
            if timeout <= 0 or timeout > 300:  # Maximum 5 minutes timeout
                return False
        
        return True

    def register_spider(self, spider: BaseSpider, config: Dict[str, Any]) -> None:
        """
        Register a spider for specific source type with validation.

        Args:
            spider: Spider instance to register
            config: Spider configuration

        Raises:
            ConfigurationException: If spider registration fails
        """
        try:
            # Validate spider implements required interface
            if not isinstance(spider, BaseSpider):
                raise ConfigurationException(
                    "Invalid spider type",
                    {"expected": "BaseSpider", "received": type(spider).__name__}
                )
            
            # Configure spider with rate limiting
            rate_config = config.get("rate_limit", {})
            spider_id = str(id(spider))
            
            # Register rate limited processor
            @limits(calls=rate_config.get("requests_per_second", 1),
                   period=1)
            async def rate_limited_processor(task: TaskConfig) -> TaskResult:
                return await spider.process(task)
            
            # Register spider
            self._spiders[spider_id] = spider
            self.register_processor(rate_limited_processor)
            
            logger.info(
                "Spider registered successfully",
                extra={"spider_id": spider_id, "config": config}
            )
            
        except Exception as e:
            logger.error(
                "Spider registration failed",
                exc=e,
                extra={"config": config}
            )
            raise ConfigurationException(
                "Failed to register spider",
                {"error": str(e), "config": config}
            )


class ScrapingTaskExecutor(BaseTaskExecutor):
    """
    Executor implementation for scraping tasks with advanced error handling
    and performance optimization.
    """

    def __init__(
        self,
        task_handler: ScrapingTask,
        metrics_collector: MetricsCollector
    ) -> None:
        """
        Initialize scraping task executor with required components.

        Args:
            task_handler: Scraping task handler instance
            metrics_collector: Metrics collection service
        """
        super().__init__(task_handler)
        self._task_handler = task_handler
        self._metrics_collector = metrics_collector
        
        logger.info("Initialized scraping task executor")

    @retry(
        retry=retry_if_exception_type(TaskException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def execute(self, task: TaskConfig) -> TaskResult:
        """
        Execute a scraping task with comprehensive error handling and monitoring.

        Args:
            task: Task configuration

        Returns:
            TaskResult: Result of scraping execution

        Raises:
            TaskException: If execution fails
            ValidationException: If task configuration is invalid
        """
        try:
            # Validate task configuration
            if not await self._task_handler.validate_config(task):
                raise ValidationException(
                    "Invalid task configuration",
                    {"task": task}
                )
            
            # Start metrics collection
            start_time = time.time()
            
            # Get appropriate spider
            spider = await self._task_handler.get_processor(task["source"])
            
            try:
                # Execute scraping with monitoring
                result = await spider.process(task)
                
                # Record metrics
                duration = time.time() - start_time
                self._metrics_collector.record_scraping_metrics(
                    task_type=self._task_handler.task_type,
                    duration=duration,
                    success=True
                )
                
                logger.info(
                    "Task execution completed",
                    extra={
                        "task": task,
                        "duration": duration,
                        "result": result
                    }
                )
                
                return result
                
            except RateLimitException:
                logger.warning(
                    "Rate limit exceeded",
                    extra={"task": task}
                )
                raise TaskException(
                    "Rate limit exceeded",
                    str(task),
                    {"retry_after": 60}
                )
                
        except Exception as e:
            # Record failure metrics
            self._metrics_collector.record_scraping_metrics(
                task_type=self._task_handler.task_type,
                success=False,
                error=str(e)
            )
            
            logger.error(
                "Task execution failed",
                exc=e,
                extra={"task": task}
            )
            raise