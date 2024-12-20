"""
Scrapy settings module for the Data Processing Pipeline's web scraping component.

This module configures Scrapy-specific settings including performance parameters,
rate limiting, security controls, and error handling mechanisms to ensure robust
and efficient web scraping operations.

Version: 1.0.0
"""

import os  # version: 3.11+
from typing import Dict, Any, List, Optional  # version: 3.11+

from config.settings import settings, debug, env
from core.types import TaskType

# Basic Scrapy Configuration
BOT_NAME = 'data_processing_pipeline'
SPIDER_MODULES = ['scraping.spiders']
NEWSPIDER_MODULE = 'scraping.spiders'

class ScrapingSettings:
    """
    Manages Scrapy settings with environment-specific configurations and security controls.
    Implements performance tuning and error handling for production-grade web scraping.
    """

    def __init__(self, env: str):
        """
        Initialize scraping settings with environment-specific configurations.

        Args:
            env (str): Current environment ('development', 'staging', 'production')
        """
        self._env = env
        self._debug = debug
        
        # Initialize base user agent
        self._user_agent = (
            'DataProcessingPipeline/1.0 '
            '(+https://github.com/your-org/data-processing-pipeline)'
        )
        
        # Configure environment-specific concurrency
        self._concurrent_requests = 32 if env == 'production' else 16
        self._concurrent_requests_per_domain = 16 if env == 'production' else 8
        self._download_delay = 1.0 if env == 'production' else 2.0

    @property
    def user_agent(self) -> str:
        """Get the configured user agent string."""
        return self._user_agent

    @property
    def concurrent_requests(self) -> int:
        """Get the maximum concurrent requests setting."""
        return self._concurrent_requests

    @property
    def download_delay(self) -> float:
        """Get the configured download delay between requests."""
        return self._download_delay

    @property
    def middlewares(self) -> List[str]:
        """Get the list of enabled middleware components."""
        return [
            'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware',
            'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware',
            'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware',
            'scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware',
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware',
            'scrapy.downloadermiddlewares.retry.RetryMiddleware',
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware',
            'scrapy.downloadermiddlewares.redirect.RedirectMiddleware',
            'scrapy.downloadermiddlewares.cookies.CookiesMiddleware',
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware',
            'scrapy.downloadermiddlewares.stats.DownloaderStats',
        ]

    @property
    def pipelines(self) -> List[str]:
        """Get the list of enabled item pipelines."""
        return [
            'scraping.pipelines.validation.ValidationPipeline',
            'scraping.pipelines.storage.StoragePipeline',
            'scraping.pipelines.monitoring.MonitoringPipeline',
        ]

    def get_retry_settings(self) -> Dict[str, Any]:
        """
        Generate retry configuration with exponential backoff.

        Returns:
            Dict[str, Any]: Complete retry configuration including backoff settings
        """
        return {
            'RETRY_ENABLED': True,
            'RETRY_TIMES': settings.max_retries,
            'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
            'RETRY_PRIORITY_ADJUST': -1,
            'RETRY_BACKOFF_ENABLED': True,
            'RETRY_BACKOFF_MAX': 60,  # Maximum backoff time in seconds
            'RETRY_BACKOFF_BASE': settings.retry_backoff,
        }

def get_scraping_settings() -> Dict[str, Any]:
    """
    Retrieve environment-specific scraping settings with performance and security configurations.

    Returns:
        Dict[str, Any]: Complete dictionary of scraping settings
    """
    scraping_settings = ScrapingSettings(env)
    
    settings_dict = {
        # Basic Configuration
        'BOT_NAME': BOT_NAME,
        'SPIDER_MODULES': SPIDER_MODULES,
        'NEWSPIDER_MODULE': NEWSPIDER_MODULE,
        
        # Security Settings
        'ROBOTSTXT_OBEY': True,
        'USER_AGENT': scraping_settings.user_agent,
        
        # Performance Settings
        'CONCURRENT_REQUESTS': scraping_settings.concurrent_requests,
        'CONCURRENT_REQUESTS_PER_DOMAIN': scraping_settings._concurrent_requests_per_domain,
        'DOWNLOAD_DELAY': scraping_settings.download_delay,
        
        # Feature Settings
        'COOKIES_ENABLED': False,
        'TELNETCONSOLE_ENABLED': False,
        
        # Timeout Settings
        'DOWNLOAD_TIMEOUT': settings.default_timeout,
        
        # Cache Settings
        'HTTPCACHE_ENABLED': env != 'production',
        'HTTPCACHE_EXPIRATION_SECS': 0 if env == 'production' else 43200,
        'HTTPCACHE_DIR': 'httpcache',
        'HTTPCACHE_IGNORE_HTTP_CODES': [503, 504, 505, 500, 502, 429],
        
        # Middleware Configuration
        'DOWNLOADER_MIDDLEWARES': {
            middleware: 500 for middleware in scraping_settings.middlewares
        },
        
        # Pipeline Configuration
        'ITEM_PIPELINES': {
            pipeline: 300 for pipeline in scraping_settings.pipelines
        },
        
        # Default Headers
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en',
        },
        
        # Retry Configuration
        **scraping_settings.get_retry_settings(),
        
        # Logging Configuration
        'LOG_LEVEL': 'DEBUG' if debug else 'INFO',
        'LOG_FORMAT': '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        'LOG_DATEFORMAT': '%Y-%m-%d %H:%M:%S',
        
        # Stats Collection
        'STATS_CLASS': 'scrapy.statscollectors.MemoryStatsCollector',
        'STATS_DUMP': True,
        
        # Memory Management
        'MEMUSAGE_ENABLED': True,
        'MEMUSAGE_LIMIT_MB': 2048,
        'MEMUSAGE_WARNING_MB': 1536,
        
        # Auto Throttling
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': scraping_settings.download_delay,
        'AUTOTHROTTLE_MAX_DELAY': 60.0,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': scraping_settings._concurrent_requests_per_domain,
        'AUTOTHROTTLE_DEBUG': debug,
    }
    
    return settings_dict

# Export configured settings instance
scraping_settings = ScrapingSettings(env)

__all__ = ['scraping_settings', 'get_scraping_settings']