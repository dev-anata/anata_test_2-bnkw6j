"""
Scrapy middleware components for the Data Processing Pipeline.

This module implements middleware components for handling request/response processing,
rate limiting, retry logic, and error handling in the web scraping pipeline.

Version: 1.0.0
"""

import time
from typing import Optional, Dict, Any, Union  # version: 3.11+
from urllib.parse import urlparse
import scrapy  # version: 2.9+
from scrapy.http import Request, Response
from scrapy.spiders import Spider
from scrapy.exceptions import IgnoreRequest

from scraping.settings import get_retry_settings, download_delay
from monitoring.logger import Logger
from core.exceptions import TaskException

class RateLimitMiddleware:
    """
    Implements adaptive rate limiting for web scraping requests.
    
    Features:
    - Per-domain rate limiting
    - Dynamic delay adjustment based on server responses
    - Automatic throttling for rate limit responses
    - Request statistics tracking
    """

    def __init__(self) -> None:
        """Initialize rate limiting middleware with dynamic rate limiting support."""
        self.download_delay = download_delay
        self.last_request_time: Dict[str, float] = {}
        self.domain_stats: Dict[str, Dict] = {}
        self.dynamic_delays: Dict[str, float] = {}
        self.logger = Logger("RateLimitMiddleware")

    def process_request(self, request: Request, spider: Spider) -> Optional[Request]:
        """
        Process and rate limit outgoing requests with dynamic adjustment.

        Args:
            request: The outgoing request
            spider: The spider instance

        Returns:
            Optional[Request]: Modified request or None
        """
        domain = urlparse(request.url).netloc
        current_time = time.time()

        # Initialize domain statistics if needed
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {
                'requests': 0,
                'errors': 0,
                'last_error_time': 0
            }

        # Get effective delay for domain
        effective_delay = self.dynamic_delays.get(domain, self.download_delay)
        
        # Check if we need to delay the request
        if domain in self.last_request_time:
            elapsed = current_time - self.last_request_time[domain]
            if elapsed < effective_delay:
                delay_needed = effective_delay - elapsed
                time.sleep(delay_needed)

        # Update tracking information
        self.last_request_time[domain] = time.time()
        self.domain_stats[domain]['requests'] += 1

        return request

    def adjust_rate_limit(self, domain: str, response_code: int) -> None:
        """
        Dynamically adjust rate limits based on server response.

        Args:
            domain: The domain being accessed
            response_code: HTTP response code received
        """
        stats = self.domain_stats[domain]
        current_delay = self.dynamic_delays.get(domain, self.download_delay)

        # Adjust delay based on response code
        if response_code == 429:  # Too Many Requests
            stats['errors'] += 1
            stats['last_error_time'] = time.time()
            new_delay = current_delay * 2
            self.dynamic_delays[domain] = min(new_delay, 60.0)  # Cap at 60 seconds
            self.logger.info(
                f"Rate limit exceeded for {domain}, increasing delay to {new_delay}s",
                {"domain": domain, "new_delay": new_delay}
            )
        elif response_code >= 500:  # Server errors
            stats['errors'] += 1
            stats['last_error_time'] = time.time()
            new_delay = current_delay * 1.5
            self.dynamic_delays[domain] = min(new_delay, 30.0)
        elif response_code == 200:  # Successful response
            # Gradually decrease delay if no recent errors
            if time.time() - stats['last_error_time'] > 300:  # 5 minutes
                new_delay = max(current_delay * 0.8, self.download_delay)
                self.dynamic_delays[domain] = new_delay


class RetryMiddleware:
    """
    Handles retry logic for failed requests with circuit breaker pattern.
    
    Features:
    - Exponential backoff retry strategy
    - Circuit breaker pattern implementation
    - Per-domain retry tracking
    - Comprehensive error handling
    """

    def __init__(self) -> None:
        """Initialize retry middleware with circuit breaker support."""
        self.retry_settings = get_retry_settings()
        self.circuit_breakers: Dict[str, Dict] = {}
        self.retry_stats: Dict[str, Dict] = {}
        self.logger = Logger("RetryMiddleware")

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Union[Request, Response]:
        """
        Process response and handle retries with circuit breaker logic.

        Args:
            request: The original request
            response: The received response
            spider: The spider instance

        Returns:
            Union[Request, Response]: Retry request or original response
        """
        domain = urlparse(request.url).netloc

        # Initialize tracking for domain if needed
        if domain not in self.retry_stats:
            self.retry_stats[domain] = {'attempts': 0, 'failures': 0}

        # Check if circuit breaker is tripped
        if self.check_circuit_breaker(domain):
            raise IgnoreRequest(f"Circuit breaker open for {domain}")

        # Check if response needs retry
        retry_codes = self.retry_settings['RETRY_HTTP_CODES']
        if response.status in retry_codes:
            retries = request.meta.get('retry_times', 0)
            if retries < self.retry_settings['RETRY_TIMES']:
                # Update retry statistics
                self.retry_stats[domain]['attempts'] += 1
                
                # Calculate backoff delay
                backoff = self.retry_settings['RETRY_BACKOFF_BASE'] ** retries
                max_backoff = self.retry_settings['RETRY_BACKOFF_MAX']
                delay = min(backoff, max_backoff)

                # Log retry attempt
                self.logger.info(
                    f"Retrying request to {domain} (attempt {retries + 1})",
                    {
                        "domain": domain,
                        "status_code": response.status,
                        "retry_count": retries + 1,
                        "delay": delay
                    }
                )

                # Create retry request
                retry_request = request.copy()
                retry_request.meta['retry_times'] = retries + 1
                retry_request.dont_filter = True
                retry_request.meta['download_timeout'] = delay
                return retry_request

            # Max retries exceeded
            self.retry_stats[domain]['failures'] += 1
            self.logger.error(
                f"Max retries exceeded for {domain}",
                {"domain": domain, "url": request.url, "status_code": response.status}
            )

        return response

    def check_circuit_breaker(self, domain: str) -> bool:
        """
        Check and update circuit breaker state.

        Args:
            domain: The domain to check

        Returns:
            bool: True if circuit breaker is open, False otherwise
        """
        if domain not in self.circuit_breakers:
            self.circuit_breakers[domain] = {
                'failures': 0,
                'last_failure_time': 0,
                'state': 'closed'
            }

        breaker = self.circuit_breakers[domain]
        current_time = time.time()

        # Reset circuit breaker if enough time has passed
        if breaker['state'] == 'open':
            if current_time - breaker['last_failure_time'] > 300:  # 5 minute timeout
                breaker['state'] = 'closed'
                breaker['failures'] = 0
                self.logger.info(f"Circuit breaker reset for {domain}")
                return False

        # Check failure threshold
        if breaker['failures'] >= 5:  # Trip after 5 failures
            breaker['state'] = 'open'
            self.logger.error(
                f"Circuit breaker tripped for {domain}",
                {"domain": domain, "failures": breaker['failures']}
            )
            return True

        return False


class LoggingMiddleware:
    """
    Enhanced logging middleware with performance metrics and trace context.
    
    Features:
    - Request/response logging with sampling
    - Performance metrics tracking
    - Distributed trace context propagation
    - Structured logging format
    """

    def __init__(self) -> None:
        """Initialize enhanced logging middleware."""
        self.request_stats: Dict[str, Dict] = {}
        self.sample_rate = 0.1  # Log 10% of requests
        self.metrics: Dict[str, Any] = {
            'requests': 0,
            'success': 0,
            'failures': 0,
            'total_time': 0
        }
        self.logger = Logger("LoggingMiddleware")

    def process_request(self, request: Request, spider: Spider) -> None:
        """
        Log request details with trace context.

        Args:
            request: The outgoing request
            spider: The spider instance
        """
        domain = urlparse(request.url).netloc
        request.meta['start_time'] = time.time()

        # Initialize domain statistics
        if domain not in self.request_stats:
            self.request_stats[domain] = {
                'requests': 0,
                'success': 0,
                'failures': 0,
                'total_time': 0
            }

        # Sample logging
        if time.time() % 10 < self.sample_rate:
            self.logger.info(
                f"Outgoing request to {domain}",
                {
                    "url": request.url,
                    "method": request.method,
                    "spider": spider.name,
                    "domain_stats": self.request_stats[domain]
                }
            )

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """
        Log response with performance metrics.

        Args:
            request: The original request
            response: The received response
            spider: The spider instance

        Returns:
            Response: The unmodified response
        """
        domain = urlparse(request.url).netloc
        duration = time.time() - request.meta['start_time']

        # Update statistics
        self.request_stats[domain]['requests'] += 1
        self.request_stats[domain]['total_time'] += duration
        
        if 200 <= response.status < 300:
            self.request_stats[domain]['success'] += 1
        else:
            self.request_stats[domain]['failures'] += 1

        # Sample logging
        if time.time() % 10 < self.sample_rate:
            self.logger.info(
                f"Response received from {domain}",
                {
                    "url": request.url,
                    "status": response.status,
                    "duration": duration,
                    "spider": spider.name,
                    "domain_stats": self.request_stats[domain]
                }
            )

        return response