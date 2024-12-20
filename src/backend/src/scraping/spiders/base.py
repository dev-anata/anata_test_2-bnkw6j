"""
Base spider class implementing core web scraping functionality with enhanced security,
performance optimization, and robust error handling.

This module provides the foundation for all web scraping tasks in the data processing
pipeline, implementing:
- Task processing interface
- Comprehensive error handling with retries
- Security controls and rate limiting
- Performance optimization
- Telemetry and monitoring

Version: 1.0.0
"""

from abc import ABC, abstractmethod  # version: 3.11+
from typing import Dict, List, Optional, Any, Iterator  # version: 3.11+
import scrapy  # version: 2.9+
from scrapy.http import Request, Response
from scrapy.exceptions import IgnoreRequest, CloseSpider

from core.interfaces import TaskProcessor
from core.types import TaskType, TaskConfig, TaskResult
from scraping.settings import scraping_settings
from monitoring.logger import Logger

# Initialize logger with security and performance features
logger = Logger('scraping.spiders.base')

class BaseSpider(scrapy.Spider, TaskProcessor, ABC):
    """
    Abstract base spider class implementing core scraping functionality with enhanced
    security, performance optimization, and robust error handling.
    
    Features:
    - Task processing interface implementation
    - Request fingerprinting and deduplication
    - Comprehensive error handling and retries
    - Rate limiting and resource optimization
    - Security controls and input validation
    - Telemetry and monitoring integration
    """

    # Default spider attributes
    name = 'base_spider'
    processor_type: TaskType = 'scrape'
    allowed_domains: List[str] = []
    start_urls: List[str] = []

    def __init__(self, config: TaskConfig) -> None:
        """
        Initialize base spider with enhanced configuration validation and security controls.

        Args:
            config: Task configuration containing scraping parameters

        Raises:
            ValidationException: If configuration is invalid
            ConfigurationException: If security checks fail
        """
        super().__init__()
        
        # Validate and store configuration
        self.config = self._validate_config(config)
        
        # Initialize security and tracking components
        self.stats: Dict[str, Any] = {}
        self.request_fingerprints: Dict[str, bool] = {}
        self.retry_counts: Dict[str, int] = {}
        
        # Configure spider settings with security and performance optimizations
        self.custom_settings = {
            'USER_AGENT': scraping_settings.user_agent,
            'CONCURRENT_REQUESTS': scraping_settings.concurrent_requests,
            'DOWNLOAD_DELAY': scraping_settings.download_delay,
            'COOKIES_ENABLED': False,  # Disable cookies for security
            'ROBOTSTXT_OBEY': True,  # Respect robots.txt
            'HTTPCACHE_ENABLED': False,  # Disable cache in production
            
            # Security headers
            'DEFAULT_REQUEST_HEADERS': {
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en',
                'DNT': '1',  # Do Not Track
            },
            
            # Error handling and retry configuration
            'RETRY_ENABLED': True,
            'RETRY_TIMES': 3,
            'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
            'RETRY_PRIORITY_ADJUST': -1,
            
            # Performance optimization
            'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
            'DOWNLOAD_TIMEOUT': 30,
            'REDIRECT_MAX_TIMES': 5,
        }
        
        logger.info(
            "Initialized spider",
            extra={
                "spider_name": self.name,
                "allowed_domains": self.allowed_domains,
                "concurrent_requests": self.custom_settings['CONCURRENT_REQUESTS']
            }
        )

    def _validate_config(self, config: TaskConfig) -> TaskConfig:
        """
        Validate task configuration with security checks.

        Args:
            config: Raw task configuration

        Returns:
            Validated configuration dictionary

        Raises:
            ValidationException: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")
            
        required_fields = ['source', 'allowed_domains']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required configuration field: {field}")
                
        # Validate and sanitize allowed domains
        if not isinstance(config['allowed_domains'], list):
            raise ValueError("allowed_domains must be a list")
            
        self.allowed_domains = [
            domain.strip().lower() 
            for domain in config['allowed_domains']
            if isinstance(domain, str) and domain.strip()
        ]
        
        return config

    def start_requests(self) -> Iterator[Request]:
        """
        Generate initial requests with enhanced security and rate limiting.

        Yields:
            Iterator[Request]: Secured and rate-limited requests
        """
        if not self.start_urls and 'source' in self.config:
            self.start_urls = [self.config['source']]
            
        for url in self.start_urls:
            # Generate request fingerprint for deduplication
            fingerprint = self._get_request_fingerprint(url)
            if fingerprint in self.request_fingerprints:
                continue
                
            self.request_fingerprints[fingerprint] = True
            
            # Create request with security headers and meta information
            yield Request(
                url=url,
                callback=self.parse,
                errback=self._handle_error,
                dont_filter=False,
                meta={
                    'fingerprint': fingerprint,
                    'retry_count': 0,
                    'download_timeout': self.custom_settings['DOWNLOAD_TIMEOUT']
                },
                headers=self.custom_settings['DEFAULT_REQUEST_HEADERS']
            )

    @abstractmethod
    def parse(self, response: Response) -> Iterator[Any]:
        """
        Abstract method for parsing responses.

        Args:
            response: Scrapy Response object

        Yields:
            Iterator[Any]: Scraped items
        """
        raise NotImplementedError("Subclasses must implement parse method")

    def _handle_error(self, failure: Any) -> None:
        """
        Handle request failures with comprehensive error tracking.

        Args:
            failure: Twisted failure object
        """
        request = failure.request
        fingerprint = request.meta.get('fingerprint', '')
        retry_count = request.meta.get('retry_count', 0)
        
        logger.error(
            "Request failed",
            extra={
                'url': request.url,
                'fingerprint': fingerprint,
                'retry_count': retry_count,
                'error': str(failure.value)
            }
        )
        
        # Update retry statistics
        self.retry_counts[fingerprint] = retry_count + 1
        
        # Raise exception if max retries exceeded
        if retry_count >= self.custom_settings['RETRY_TIMES']:
            raise CloseSpider(f"Max retries exceeded for {request.url}")

    def _get_request_fingerprint(self, url: str) -> str:
        """
        Generate unique fingerprint for request deduplication.

        Args:
            url: Request URL

        Returns:
            str: Unique request fingerprint
        """
        from hashlib import sha256
        return sha256(url.encode()).hexdigest()

    async def process(self, task: TaskConfig) -> TaskResult:
        """
        Process scraping task with comprehensive error handling and monitoring.

        Args:
            task: Task configuration

        Returns:
            TaskResult: Result of scraping task with detailed statistics

        Raises:
            TaskException: If processing fails
        """
        try:
            # Initialize task processing
            logger.info("Starting task processing", extra={"task": task})
            
            # Configure spider for task
            self.config = self._validate_config(task)
            
            # Execute scraping process
            runner = scrapy.crawler.CrawlerRunner(self.custom_settings)
            await runner.crawl(self.__class__, config=task)
            
            # Collect and return results
            result = {
                'status': 'completed',
                'stats': dict(self.stats),
                'errors': list(self.retry_counts.items()),
                'items_scraped': self.stats.get('item_scraped_count', 0)
            }
            
            logger.info("Task completed", extra={"result": result})
            return result
            
        except Exception as e:
            logger.error(
                "Task processing failed",
                exc=e,
                extra={"task": task}
            )
            raise

    def closed(self, reason: Optional[str]) -> None:
        """
        Handle spider closure with comprehensive cleanup.

        Args:
            reason: Reason for spider closure
        """
        logger.info(
            "Spider closed",
            extra={
                "reason": reason,
                "stats": dict(self.stats),
                "retry_counts": dict(self.retry_counts)
            }
        )
        
        # Clear tracking dictionaries
        self.request_fingerprints.clear()
        self.retry_counts.clear()