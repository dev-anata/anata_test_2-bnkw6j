"""
Web scraping module initialization for the Data Processing Pipeline.

This module provides a high-performance, production-ready web scraping framework
with modular architecture for content extraction and processing. It supports
concurrent processing capabilities to achieve 100+ pages/minute throughput
while maintaining 98% data accuracy.

Version: 1.0.0
"""

from typing import Dict, Any, Optional, Type  # version: 3.11+

# Import core scraping components
from scraping.settings import scraping_settings
from scraping.extractors import (
    BaseExtractor,
    TextExtractor,
    TableExtractor,
    create_extractor
)
from scraping.pipelines import (
    BasePipeline,
    TextPipeline,
    TablePipeline,
    create_pipeline
)

# Module version
__version__ = '1.0.0'

# Configure module-level settings
DEFAULT_SETTINGS = {
    'user_agent': scraping_settings.user_agent,
    'concurrent_requests': scraping_settings.concurrent_requests,
    'download_delay': scraping_settings.download_delay
}

# Type registry for content extractors
EXTRACTOR_REGISTRY: Dict[str, Type[BaseExtractor]] = {
    'text': TextExtractor,
    'table': TableExtractor
}

# Type registry for processing pipelines
PIPELINE_REGISTRY: Dict[str, Type[BasePipeline]] = {
    'text': TextPipeline,
    'table': TablePipeline
}

def get_extractor(
    extractor_type: str,
    config: Optional[Dict[str, Any]] = None
) -> BaseExtractor:
    """
    Get configured extractor instance for specified content type.
    
    Args:
        extractor_type: Type of content extractor ('text' or 'table')
        config: Optional extractor configuration
        
    Returns:
        BaseExtractor: Configured extractor instance
        
    Raises:
        ValidationException: If extractor type is invalid
    """
    return create_extractor(extractor_type, config or {})

def get_pipeline(
    pipeline_type: str,
    storage_backend: Any,
    config: Optional[Dict[str, Any]] = None
) -> BasePipeline:
    """
    Get configured pipeline instance for specified content type.
    
    Args:
        pipeline_type: Type of processing pipeline ('text' or 'table')
        storage_backend: Storage backend for data persistence
        config: Optional pipeline configuration
        
    Returns:
        BasePipeline: Configured pipeline instance
        
    Raises:
        ValidationException: If pipeline type is invalid
    """
    return create_pipeline(pipeline_type, storage_backend, config or {})

# Export public interface
__all__ = [
    # Version info
    '__version__',
    
    # Core extractors
    'BaseExtractor',
    'TextExtractor',
    'TableExtractor',
    'create_extractor',
    'get_extractor',
    
    # Processing pipelines
    'BasePipeline',
    'TextPipeline',
    'TablePipeline',
    'create_pipeline',
    'get_pipeline',
    
    # Configuration
    'scraping_settings',
    'DEFAULT_SETTINGS'
]