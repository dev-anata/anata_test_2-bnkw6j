"""
Spider package initialization module providing a thread-safe registry for web scraping spiders
with comprehensive validation, monitoring, and type safety features.

This module implements:
- Thread-safe spider registration system
- Comprehensive spider validation
- LRU caching for spider class lookups
- Detailed logging and monitoring
- Type safety through static typing

Version: 1.0.0
"""

from typing import Dict, Type, Optional  # version: 3.11+
from threading import Lock  # version: 3.11+
from cachetools import LRUCache  # version: 5.3+
import logging  # version: 3.11+

from scraping.spiders.base import BaseSpider
from core.types import TaskType
from core.exceptions import ValidationException, ConfigurationException

# Initialize logger with security and monitoring features
logger = logging.getLogger(__name__)

# Thread-safe spider registry
SPIDER_REGISTRY: Dict[str, Type[BaseSpider]] = {}
_registry_lock = Lock()

# LRU cache for frequently accessed spider classes
_spider_cache = LRUCache(maxsize=100)

def validate_spider_class(spider_class: Type[BaseSpider]) -> bool:
    """
    Comprehensive validation of spider class implementation.

    Args:
        spider_class: Spider class to validate

    Returns:
        bool: True if validation passes

    Raises:
        ValidationException: If spider class fails validation
    """
    try:
        # Verify BaseSpider inheritance
        if not issubclass(spider_class, BaseSpider):
            raise ValidationException(
                "Spider class must inherit from BaseSpider",
                {"class": spider_class.__name__}
            )

        # Validate required attributes
        if not hasattr(spider_class, 'name') or not spider_class.name:
            raise ValidationException(
                "Spider class must define 'name' attribute",
                {"class": spider_class.__name__}
            )

        if not hasattr(spider_class, 'processor_type'):
            raise ValidationException(
                "Spider class must define 'processor_type' attribute",
                {"class": spider_class.__name__}
            )

        # Validate processor type
        if spider_class.processor_type != 'scrape':
            raise ValidationException(
                "Invalid processor type for spider",
                {
                    "class": spider_class.__name__,
                    "expected": "scrape",
                    "received": spider_class.processor_type
                }
            )

        # Validate spider name format
        if not isinstance(spider_class.name, str) or not spider_class.name.isidentifier():
            raise ValidationException(
                "Spider name must be a valid Python identifier",
                {"class": spider_class.__name__, "name": spider_class.name}
            )

        # Verify required method implementations
        required_methods = ['parse', 'process']
        for method in required_methods:
            if not hasattr(spider_class, method) or not callable(getattr(spider_class, method)):
                raise ValidationException(
                    f"Spider class must implement '{method}' method",
                    {"class": spider_class.__name__}
                )

        logger.debug(
            "Spider class validation successful",
            extra={
                "spider_name": spider_class.name,
                "spider_class": spider_class.__name__
            }
        )
        return True

    except Exception as e:
        logger.error(
            "Spider class validation failed",
            extra={
                "spider_class": spider_class.__name__,
                "error": str(e)
            }
        )
        raise

def register_spider(spider_class: Type[BaseSpider]) -> Type[BaseSpider]:
    """
    Thread-safe registration of spider classes with comprehensive validation.

    Args:
        spider_class: Spider class to register

    Returns:
        Type[BaseSpider]: The registered spider class for decorator usage

    Raises:
        ValidationException: If spider validation fails
        ConfigurationException: If spider registration fails
    """
    try:
        # Validate spider class implementation
        validate_spider_class(spider_class)

        with _registry_lock:
            # Check for naming conflicts
            if spider_class.name in SPIDER_REGISTRY:
                raise ConfigurationException(
                    "Spider name already registered",
                    {
                        "name": spider_class.name,
                        "existing_class": SPIDER_REGISTRY[spider_class.name].__name__,
                        "new_class": spider_class.__name__
                    }
                )

            # Register spider class
            SPIDER_REGISTRY[spider_class.name] = spider_class
            
            # Clear cache entry if exists
            if spider_class.name in _spider_cache:
                del _spider_cache[spider_class.name]

            logger.info(
                "Spider registered successfully",
                extra={
                    "spider_name": spider_class.name,
                    "spider_class": spider_class.__name__
                }
            )

            return spider_class

    except Exception as e:
        logger.error(
            "Spider registration failed",
            extra={
                "spider_class": spider_class.__name__,
                "error": str(e)
            }
        )
        raise

def get_spider_class(spider_name: str) -> Type[BaseSpider]:
    """
    Retrieve a spider class from the registry with caching and validation.

    Args:
        spider_name: Name of the spider class to retrieve

    Returns:
        Type[BaseSpider]: The requested spider class

    Raises:
        KeyError: If spider name not found in registry
        ValidationException: If cached spider class fails validation
    """
    try:
        # Check cache first
        if spider_name in _spider_cache:
            spider_class = _spider_cache[spider_name]
            # Validate cached class
            if validate_spider_class(spider_class):
                return spider_class

        with _registry_lock:
            if spider_name not in SPIDER_REGISTRY:
                raise KeyError(f"Spider '{spider_name}' not found in registry")

            spider_class = SPIDER_REGISTRY[spider_name]
            
            # Validate before returning
            if validate_spider_class(spider_class):
                # Update cache
                _spider_cache[spider_name] = spider_class
                return spider_class

    except Exception as e:
        logger.error(
            "Failed to retrieve spider class",
            extra={
                "spider_name": spider_name,
                "error": str(e)
            }
        )
        raise

# Export public interface
__all__ = [
    'BaseSpider',
    'register_spider',
    'get_spider_class',
    'validate_spider_class'
]