"""
Core OCR processing module implementing document text extraction capabilities.

This module provides enterprise-grade OCR processing using Tesseract with robust
validation, error handling, and performance monitoring. Supports both synchronous
and asynchronous processing with configurable preprocessing options.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
from typing import Dict, Any, Optional, List  # version: 3.11+
import logging  # version: 3.11+
from pathlib import Path  # version: 3.11+
import time  # version: 3.11+

import pytesseract  # version: 0.3.10
from PIL import Image, ImageEnhance, ImageFilter  # version: 10.0.0
import numpy as np  # version: 1.24.0

from ocr.validators import OCRTaskConfigSchema
from core.exceptions import ValidationException

# Global configuration constants
DEFAULT_OCR_CONFIG = {
    'lang': 'eng',
    'config': '--psm 3',  # Fully automatic page segmentation
    'timeout': 300  # 5 minutes max processing time
}

SUPPORTED_IMAGE_FORMATS = ['png', 'jpg', 'jpeg', 'tiff', 'bmp']
SUPPORTED_OUTPUT_FORMATS = ['txt', 'json', 'xml', 'hocr']
MIN_CONFIDENCE_SCORE = 0.85

# Configure logging
logger = logging.getLogger(__name__)

def preprocess_image(image: Image.Image, preprocessing_config: Optional[Dict[str, Any]] = None) -> Image.Image:
    """
    Prepare image for OCR processing by applying enhancement techniques.
    
    Args:
        image: PIL Image object to preprocess
        preprocessing_config: Optional configuration for preprocessing steps
        
    Returns:
        PIL.Image: Enhanced image ready for OCR processing
        
    Raises:
        ValidationException: If image processing fails
    """
    try:
        # Convert to grayscale if not already
        if image.mode != 'L':
            image = image.convert('L')
            
        # Apply default preprocessing if no config provided
        config = preprocessing_config or {
            'denoise': True,
            'contrast': 1.5,
            'sharpen': 1.3,
            'deskew': True
        }
        
        # Denoise using Gaussian blur
        if config.get('denoise'):
            image = image.filter(ImageFilter.GaussianBlur(radius=1))
            
        # Enhance contrast
        if config.get('contrast'):
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(float(config['contrast']))
            
        # Sharpen image
        if config.get('sharpen'):
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(float(config['sharpen']))
            
        # Apply adaptive thresholding
        if config.get('threshold'):
            np_image = np.array(image)
            binary = cv2.adaptiveThreshold(
                np_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            image = Image.fromarray(binary)
            
        return image
        
    except Exception as e:
        raise ValidationException(
            "Image preprocessing failed",
            {"error": str(e), "stage": "preprocessing"}
        )

def validate_output(ocr_result: Dict[str, Any]) -> bool:
    """
    Validate OCR output quality and confidence scores.
    
    Args:
        ocr_result: Dictionary containing OCR results and metadata
        
    Returns:
        bool: True if output meets quality thresholds
        
    Raises:
        ValidationException: If validation fails
    """
    try:
        # Check confidence score
        if ocr_result.get('confidence', 0) < MIN_CONFIDENCE_SCORE * 100:
            return False
            
        # Validate text content
        text = ocr_result.get('text', '')
        if not text or len(text.strip()) == 0:
            return False
            
        # Check for common OCR errors
        error_indicators = ['?', '#', '@', '$']
        error_count = sum(text.count(c) for c in error_indicators)
        if error_count / len(text) > 0.1:  # More than 10% error characters
            return False
            
        # Validate character encoding
        try:
            text.encode('utf-8')
        except UnicodeError:
            return False
            
        return True
        
    except Exception as e:
        raise ValidationException(
            "OCR output validation failed",
            {"error": str(e), "stage": "validation"}
        )

class OCRProcessor:
    """
    Main OCR processor class implementing document text extraction.
    
    Provides both synchronous and asynchronous processing capabilities with
    comprehensive error handling and performance monitoring.
    """
    
    def __init__(self, config: OCRTaskConfigSchema):
        """
        Initialize OCR processor with configuration.
        
        Args:
            config: Validated configuration schema
            
        Raises:
            ValidationException: If configuration is invalid
        """
        self._config = config
        self._tesseract_config = {
            'lang': ','.join(config.languages) if config.languages else DEFAULT_OCR_CONFIG['lang'],
            'config': config.processing_options.get('config', DEFAULT_OCR_CONFIG['config']),
            'timeout': config.timeout_seconds or DEFAULT_OCR_CONFIG['timeout']
        }
        self._processing_lock = asyncio.Lock()
        
        # Validate Tesseract installation
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            raise ValidationException(
                "Tesseract OCR not properly configured",
                {"error": str(e)}
            )

    async def async_process_document(self, task_id: str) -> Dict[str, Any]:
        """
        Asynchronously process document with OCR.
        
        Args:
            task_id: Unique identifier for the processing task
            
        Returns:
            Dict[str, Any]: Extraction results and metadata
            
        Raises:
            ValidationException: If processing fails
        """
        async with self._processing_lock:
            start_time = time.time()
            
            try:
                logger.info(f"Starting OCR processing for task {task_id}")
                
                # Process document
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.process_document, task_id
                )
                
                processing_time = time.time() - start_time
                logger.info(f"OCR processing completed in {processing_time:.2f}s")
                
                # Add performance metrics
                result['performance'] = {
                    'processing_time_seconds': processing_time,
                    'timeout_seconds': self._tesseract_config['timeout']
                }
                
                return result
                
            except Exception as e:
                logger.error(f"OCR processing failed for task {task_id}: {str(e)}")
                raise ValidationException(
                    "Async OCR processing failed",
                    {
                        "task_id": task_id,
                        "error": str(e),
                        "processing_time": time.time() - start_time
                    }
                )

    def process_document(self, task_id: str) -> Dict[str, Any]:
        """
        Process document and extract text using OCR.
        
        Args:
            task_id: Unique identifier for the processing task
            
        Returns:
            Dict[str, Any]: Extracted text and metadata
            
        Raises:
            ValidationException: If processing fails
        """
        try:
            # Load and validate input image
            image_path = Path(self._config.source_path)
            if not image_path.exists():
                raise ValidationException(
                    "Input file not found",
                    {"path": str(image_path)}
                )
                
            # Load image
            image = Image.open(image_path)
            
            # Preprocess image
            if self._config.enable_preprocessing:
                image = preprocess_image(image, self._config.processing_options.get('preprocessing'))
                
            # Extract text
            ocr_result = self.extract_text(image)
            
            # Validate output quality
            if not validate_output(ocr_result):
                raise ValidationException(
                    "OCR output failed quality validation",
                    {"confidence": ocr_result.get('confidence')}
                )
                
            # Format output according to specified format
            formatted_result = self._format_output(ocr_result)
            
            return {
                'task_id': task_id,
                'result': formatted_result,
                'metadata': {
                    'confidence': ocr_result.get('confidence'),
                    'language': self._tesseract_config['lang'],
                    'source_file': str(image_path),
                    'processing_options': self._config.processing_options
                }
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            raise ValidationException(
                "Document processing failed",
                {"task_id": task_id, "error": str(e)}
            )

    def extract_text(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract text from preprocessed image.
        
        Args:
            image: Preprocessed PIL Image object
            
        Returns:
            Dict[str, Any]: Extracted text and confidence scores
            
        Raises:
            ValidationException: If text extraction fails
        """
        try:
            # Extract text with confidence data
            result = pytesseract.image_to_data(
                image,
                lang=self._tesseract_config['lang'],
                config=self._tesseract_config['config'],
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [float(c) for c in result['conf'] if c != '-1']
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'text': ' '.join(result['text']),
                'confidence': avg_confidence,
                'words': list(zip(result['text'], result['conf'])),
                'boxes': list(zip(result['left'], result['top'], 
                                result['width'], result['height']))
            }
            
        except Exception as e:
            raise ValidationException(
                "Text extraction failed",
                {"error": str(e)}
            )

    def _format_output(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format OCR results according to specified output format.
        
        Args:
            ocr_result: Raw OCR extraction results
            
        Returns:
            Dict[str, Any]: Formatted results
            
        Raises:
            ValidationException: If formatting fails
        """
        try:
            output_format = self._config.output_format.lower()
            
            if output_format == 'txt':
                return {'text': ocr_result['text']}
                
            elif output_format == 'json':
                return {
                    'text': ocr_result['text'],
                    'words': ocr_result['words'],
                    'boxes': ocr_result['boxes'],
                    'confidence': ocr_result['confidence']
                }
                
            elif output_format == 'xml':
                # Implement XML formatting if needed
                raise NotImplementedError("XML output format not implemented")
                
            elif output_format == 'hocr':
                # Implement hOCR formatting if needed
                raise NotImplementedError("hOCR output format not implemented")
                
            else:
                raise ValidationException(
                    "Unsupported output format",
                    {"format": output_format}
                )
                
        except Exception as e:
            raise ValidationException(
                "Output formatting failed",
                {"error": str(e), "format": self._config.output_format}
            )

__all__ = [
    'OCRProcessor',
    'preprocess_image',
    'validate_output',
    'DEFAULT_OCR_CONFIG',
    'SUPPORTED_IMAGE_FORMATS',
    'SUPPORTED_OUTPUT_FORMATS'
]