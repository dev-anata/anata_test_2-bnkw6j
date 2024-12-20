"""
Distributed rate limiter implementation using Redis for API request throttling.

This module implements a sliding window rate limiting algorithm using Redis as the
backend store, enabling distributed rate limiting across multiple application instances.
The implementation supports per-client rate limits with configurable windows and limits.

Version: 1.0.0
"""

import time  # version: 3.11+
from typing import Dict, Optional  # version: 3.11+
import redis  # version: 4.5+

from core.exceptions import PipelineException
from config.settings import settings

class RateLimitExceeded(PipelineException):
    """
    Exception raised when a client exceeds their rate limit.
    
    Attributes:
        message (str): Human-readable error description
        retry_after (int): Seconds until the rate limit window resets
    """
    
    def __init__(self, message: str, retry_after: int) -> None:
        """
        Initialize rate limit exception with retry information.
        
        Args:
            message: Human-readable error message
            retry_after: Seconds until the rate limit resets
        """
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """
    Distributed rate limiter using Redis sliding window implementation.
    
    Implements a sliding window rate limiting algorithm that provides precise
    rate limiting while being memory efficient. Uses Redis sorted sets to
    track request timestamps within the sliding window.
    
    Attributes:
        max_requests (int): Maximum number of requests allowed per window
        window_size (int): Size of the sliding window in seconds
    """

    def __init__(self, 
                 max_requests: Optional[int] = None,
                 window_size: Optional[int] = None) -> None:
        """
        Initialize the rate limiter with Redis connection and limits.
        
        Args:
            max_requests: Maximum requests per window, defaults to settings value
            window_size: Window size in seconds, defaults to settings value
        """
        # Initialize Redis connection pool
        self._redis_pool = redis.ConnectionPool(
            **settings.REDIS_CONFIG,
            decode_responses=True
        )
        self._redis_client = redis.Redis(connection_pool=self._redis_pool)
        
        # Set rate limiting parameters
        self.max_requests = max_requests or settings.API_RATE_LIMIT_MAX_REQUESTS
        self.window_size = window_size or settings.API_RATE_LIMIT_WINDOW_SIZE
        
        # Key prefix for rate limit entries
        self._key_prefix = "rate_limit:"

    def check_rate_limit(self, client_id: str) -> bool:
        """
        Check if a request from the client is within rate limits.
        
        Implements a sliding window algorithm using Redis sorted sets to track
        request timestamps. Automatically removes expired entries and enforces
        the configured rate limit.
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            bool: True if request is allowed, False if rate limit exceeded
            
        Raises:
            RateLimitExceeded: When client has exceeded their rate limit
        """
        redis_key = f"{self._key_prefix}{client_id}"
        current_time = int(time.time())
        window_start = current_time - self.window_size
        
        try:
            # Execute Redis transaction for atomic updates
            with self._redis_client.pipeline() as pipe:
                while True:
                    try:
                        # Watch the key for changes
                        pipe.watch(redis_key)
                        
                        # Remove timestamps outside the window
                        pipe.zremrangebyscore(redis_key, 0, window_start)
                        
                        # Count requests in current window
                        request_count = pipe.zcard(redis_key)
                        
                        # Start transaction
                        pipe.multi()
                        
                        if request_count and request_count.execute()[0] >= self.max_requests:
                            # Get oldest timestamp to calculate retry-after
                            oldest_timestamp = pipe.zrange(redis_key, 0, 0)
                            if oldest_timestamp:
                                retry_after = int(oldest_timestamp[0]) + self.window_size - current_time
                            else:
                                retry_after = self.window_size
                                
                            raise RateLimitExceeded(
                                f"Rate limit exceeded. Maximum {self.max_requests} "
                                f"requests per {self.window_size} seconds allowed.",
                                retry_after=retry_after
                            )
                        
                        # Add new request timestamp
                        pipe.zadd(redis_key, {str(current_time): current_time})
                        
                        # Set key expiration
                        pipe.expire(redis_key, self.window_size)
                        
                        # Execute transaction
                        pipe.execute()
                        break
                        
                    except redis.WatchError:
                        # Key modified, retry transaction
                        continue
                    
            return True
            
        except redis.RedisError as e:
            # Log Redis errors but don't block requests
            # In case of Redis failures, we fail open but with logging
            return True

    def get_remaining_requests(self, client_id: str) -> Dict[str, int]:
        """
        Get remaining allowed requests and time until window reset.
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            Dict containing:
                remaining_requests: Number of requests remaining in window
                reset_time: Seconds until the oldest request expires
        """
        redis_key = f"{self._key_prefix}{client_id}"
        current_time = int(time.time())
        window_start = current_time - self.window_size
        
        try:
            # Remove expired entries and count current requests
            with self._redis_client.pipeline() as pipe:
                pipe.zremrangebyscore(redis_key, 0, window_start)
                pipe.zcard(redis_key)
                pipe.zrange(redis_key, 0, 0)
                _, request_count, oldest = pipe.execute()
                
                remaining = max(0, self.max_requests - request_count)
                
                # Calculate reset time from oldest request
                if oldest:
                    reset_time = int(oldest[0]) + self.window_size - current_time
                else:
                    reset_time = 0
                    
                return {
                    "remaining_requests": remaining,
                    "reset_time": reset_time
                }
                
        except redis.RedisError:
            # Return conservative estimate on Redis errors
            return {
                "remaining_requests": 0,
                "reset_time": self.window_size
            }