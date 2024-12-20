"""
OCR package initialization module exposing core OCR processing capabilities.

This module provides a unified interface for OCR processing with support for text
and table extraction, enhanced error handling, and performance monitoring. Implements
enterprise-grade OCR processing with 98% accuracy target.

Version: 1.0.0
"""

from typing import Dict, Any, Optional, Type, Union  # version: 3.11+
import structlog  # version: 23.1.0

from ocr.engine import OCREngine, EXTRACTOR_REGISTRY, DEFAULT_ENGINE_CONFIG
from ocr.processors import (
    OCRProcessor, preprocess_image, validate_output,
    DEFAULT_OCR_CONFIG, SUPPORTED_IMAGE_FORMATS, SUPPORTED_OUTPUT_FORMATS
)
from ocr.extractors import (
    BaseExtractor, TextExtractor, TableExtractor,
    EXTRACTION_TYPES, TEXT_CONFIDENCE_THRESHOLD, TABLE_CONFIDENCE_THRESHOLD
)

# Package version
__version__ = "1.0.0"

# Configure structured logging
logger = structlog.get_logger(__name__)

# Export public interface
__all__ = [
    # Core OCR engine
    'OCREngine',
    'DEFAULT_ENGINE_CONFIG',
    'EXTRACTOR_REGISTRY',
    
    # OCR processors
    'OCRProcessor',
    'preprocess_image',
    'validate_output',
    'DEFAULT_OCR_CONFIG',
    'SUPPORTED_IMAGE_FORMATS',
    'SUPPORTED_OUTPUT_FORMATS',
    
    # Extractors
    'BaseExtractor',
    'TextExtractor', 
    'TableExtractor',
    'EXTRACTION_TYPES',
    'TEXT_CONFIDENCE_THRESHOLD',
    'TABLE_CONFIDENCE_THRESHOLD'
]

# Initialize logging with package context
logger.info(
    "OCR package initialized",
    version=__version__,
    supported_formats=SUPPORTED_IMAGE_FORMATS,
    extraction_types=EXTRACTION_TYPES,
    confidence_thresholds={
        "text": TEXT_CONFIDENCE_THRESHOLD,
        "table": TABLE_CONFIDENCE_THRESHOLD
    }
)

def get_extractor(extraction_type: str, config: Dict[str, Any]) -> BaseExtractor:
    """
    Factory function to get appropriate extractor instance.
    
    Args:
        extraction_type: Type of extraction required (text/table)
        config: Extraction configuration parameters
        
    Returns:
        BaseExtractor: Configured extractor instance
        
    Raises:
        ValidationException: If extraction type is invalid
    """
    if extraction_type not in EXTRACTION_TYPES:
        logger.error(
            "Invalid extraction type requested",
            extraction_type=extraction_type,
            supported_types=EXTRACTION_TYPES
        )
        raise ValueError(f"Unsupported extraction type: {extraction_type}")
        
    extractor_class = {
        "text": TextExtractor,
        "table": TableExtractor
    }.get(extraction_type)
    
    logger.debug(
        "Creating extractor instance",
        type=extraction_type,
        config=config
    )
    
    return extractor_class(config)

def validate_extraction_config(config: Dict[str, Any]) -> bool:
    """
    Validate extraction configuration parameters.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        bool: True if configuration is valid
        
    Raises:
        ValidationException: If configuration is invalid
    """
    required_fields = {"source_path", "output_format"}
    
    # Check required fields
    if not all(field in config for field in required_fields):
        logger.error(
            "Missing required configuration fields",
            required=required_fields,
            provided=set(config.keys())
        )
        return False
        
    # Validate source format
    source_ext = config["source_path"].split(".")[-1].lower()
    if source_ext not in SUPPORTED_IMAGE_FORMATS:
        logger.error(
            "Unsupported source format",
            format=source_ext,
            supported=SUPPORTED_IMAGE_FORMATS
        )
        return False
        
    # Validate output format
    if config["output_format"] not in SUPPORTED_OUTPUT_FORMATS:
        logger.error(
            "Unsupported output format",
            format=config["output_format"],
            supported=SUPPORTED_OUTPUT_FORMATS
        )
        return False
        
    return True

# Register signal handlers for graceful shutdown
import signal
import sys

def shutdown_handler(signum, frame):
    """Handle graceful shutdown of OCR processing."""
    logger.warning(
        "Shutdown signal received",
        signal=signal.Signals(signum).name
    )
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)