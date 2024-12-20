"""
Validation module for OCR-related tasks and configurations.

This module provides comprehensive validation for OCR task configurations,
input data, and processing parameters to ensure they meet system requirements
before processing begins.

Version: 1.0.0
"""

from pathlib import Path  # version: 3.11+
from typing import Dict, List, Optional, Any, Union  # version: 3.11+
from pydantic import BaseModel, Field, validator, root_validator  # version: 2.0+

from core.exceptions import ValidationException
from core.schemas import TaskCreateSchema

# Supported file formats for OCR processing
SUPPORTED_FORMATS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff'}

# Supported output formats
SUPPORTED_OUTPUT_FORMATS = {'txt', 'json', 'xml', 'hocr'}

# Default OCR processing parameters
DEFAULT_PROCESSING_OPTIONS = {
    'dpi': 300,
    'page_segmentation_mode': 3,  # Fully automatic page segmentation
    'ocr_engine_mode': 3,  # Default Tesseract engine mode
    'language': 'eng'
}

# Maximum file size in MB (configurable)
MAX_FILE_SIZE_MB = 100

class OCRTaskConfigSchema(BaseModel):
    """
    Pydantic schema for validating OCR task configurations.
    
    Attributes:
        source_path (str): Path to the input file for OCR processing
        output_format (str): Desired output format (txt, json, xml, hocr)
        languages (Optional[List[str]]): List of language codes for OCR
        processing_options (Optional[Dict[str, Any]]): Additional OCR parameters
        timeout_seconds (Optional[int]): Processing timeout in seconds
        enable_preprocessing (Optional[bool]): Enable image preprocessing
    """
    source_path: str = Field(..., description="Path to input file for OCR")
    output_format: str = Field(..., description="Desired output format")
    languages: Optional[List[str]] = Field(
        default=['eng'],
        description="Language codes for OCR processing"
    )
    processing_options: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: DEFAULT_PROCESSING_OPTIONS.copy(),
        description="OCR processing parameters"
    )
    timeout_seconds: Optional[int] = Field(
        default=300,
        gt=0,
        le=3600,
        description="Processing timeout in seconds"
    )
    enable_preprocessing: Optional[bool] = Field(
        default=True,
        description="Enable image preprocessing"
    )

    @validator('source_path')
    def validate_source_path(cls, value: str) -> str:
        """
        Validate the source file path exists and has supported format.
        
        Args:
            value: File path to validate
            
        Returns:
            str: Validated absolute file path
            
        Raises:
            ValidationException: If path is invalid or file format unsupported
        """
        try:
            path = Path(value).resolve()
            
            # Security check for path traversal
            if '..' in path.parts:
                raise ValidationException(
                    "Path traversal detected",
                    {"path": str(path)}
                )
            
            # Check file exists and is accessible
            if not path.is_file():
                raise ValidationException(
                    "File does not exist or is not accessible",
                    {"path": str(path)}
                )
            
            # Validate file extension
            if path.suffix.lower() not in SUPPORTED_FORMATS:
                raise ValidationException(
                    "Unsupported file format",
                    {
                        "path": str(path),
                        "supported_formats": list(SUPPORTED_FORMATS)
                    }
                )
            
            # Check file is not empty
            if path.stat().st_size == 0:
                raise ValidationException(
                    "File is empty",
                    {"path": str(path)}
                )
            
            return str(path)
            
        except (OSError, ValueError) as e:
            raise ValidationException(
                "Invalid file path",
                {"path": value, "error": str(e)}
            )

    @validator('output_format')
    def validate_output_format(cls, value: str) -> str:
        """
        Validate the output format is supported.
        
        Args:
            value: Output format to validate
            
        Returns:
            str: Validated output format
            
        Raises:
            ValidationException: If format is unsupported
        """
        format_lower = value.lower()
        if format_lower not in SUPPORTED_OUTPUT_FORMATS:
            raise ValidationException(
                "Unsupported output format",
                {
                    "format": value,
                    "supported_formats": list(SUPPORTED_OUTPUT_FORMATS)
                }
            )
        return format_lower

    @validator('languages')
    def validate_languages(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """
        Validate language codes are supported by Tesseract.
        
        Args:
            value: List of language codes to validate
            
        Returns:
            Optional[List[str]]: Validated language list
            
        Raises:
            ValidationException: If languages are invalid or unsupported
        """
        if not value:
            return ['eng']
            
        # Validate each language code
        for lang in value:
            if not isinstance(lang, str) or len(lang) != 3:
                raise ValidationException(
                    "Invalid language code format",
                    {"language": lang, "expected_format": "3-letter ISO code"}
                )
            
            # TODO: Add check against installed Tesseract language data files
            # This would be implementation-specific based on system setup
            
        return [lang.lower() for lang in value]

    @validator('processing_options')
    def validate_processing_options(cls, value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate OCR processing options and their compatibility.
        
        Args:
            value: Processing options to validate
            
        Returns:
            Dict[str, Any]: Validated processing options
            
        Raises:
            ValidationException: If options are invalid or incompatible
        """
        if value is None:
            return DEFAULT_PROCESSING_OPTIONS.copy()
            
        validated_options = DEFAULT_PROCESSING_OPTIONS.copy()
        validated_options.update(value)
        
        # Validate DPI setting
        if not isinstance(validated_options['dpi'], int) or not (72 <= validated_options['dpi'] <= 1200):
            raise ValidationException(
                "Invalid DPI value",
                {"dpi": validated_options['dpi'], "valid_range": "72-1200"}
            )
        
        # Validate page segmentation mode
        if not isinstance(validated_options['page_segmentation_mode'], int) or \
           not (0 <= validated_options['page_segmentation_mode'] <= 13):
            raise ValidationException(
                "Invalid page segmentation mode",
                {"mode": validated_options['page_segmentation_mode'], "valid_range": "0-13"}
            )
        
        # Validate OCR engine mode
        if not isinstance(validated_options['ocr_engine_mode'], int) or \
           not (0 <= validated_options['ocr_engine_mode'] <= 3):
            raise ValidationException(
                "Invalid OCR engine mode",
                {"mode": validated_options['ocr_engine_mode'], "valid_range": "0-3"}
            )
        
        return validated_options

def validate_ocr_task(task_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive validation of OCR task configuration and parameters.
    
    Args:
        task_config: Configuration dictionary to validate
        
    Returns:
        Dict[str, Any]: Validated configuration dictionary
        
    Raises:
        ValidationException: If validation fails
    """
    try:
        # Create and validate schema
        config_schema = OCRTaskConfigSchema(**task_config)
        
        # Validate file size
        if not validate_file_size(config_schema.source_path):
            raise ValidationException(
                "File size exceeds maximum limit",
                {
                    "path": config_schema.source_path,
                    "max_size_mb": MAX_FILE_SIZE_MB
                }
            )
        
        # Return validated configuration as dictionary
        return config_schema.dict(exclude_none=True)
        
    except Exception as e:
        raise ValidationException(
            "OCR task validation failed",
            {"error": str(e)}
        )

def validate_file_size(file_path: str, max_size_mb: Optional[int] = None) -> bool:
    """
    Validate input file size is within acceptable limits.
    
    Args:
        file_path: Path to file to check
        max_size_mb: Optional custom size limit in MB
        
    Returns:
        bool: True if file size is acceptable
        
    Raises:
        ValidationException: If file size check fails
    """
    try:
        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        size_limit = max_size_mb or MAX_FILE_SIZE_MB
        
        return file_size_mb <= size_limit
        
    except OSError as e:
        raise ValidationException(
            "File size check failed",
            {"path": file_path, "error": str(e)}
        )

__all__ = [
    'OCRTaskConfigSchema',
    'validate_ocr_task',
    'validate_file_size',
    'SUPPORTED_FORMATS',
    'SUPPORTED_OUTPUT_FORMATS',
    'DEFAULT_PROCESSING_OPTIONS'
]