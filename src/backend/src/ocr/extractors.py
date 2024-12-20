"""
OCR content extraction module implementing specialized extraction strategies.

This module provides enterprise-grade implementations for extracting text and tabular
content from documents using OCR, with robust validation and accuracy checks.

Version: 1.0.0
"""

from abc import ABC, abstractmethod  # version: 3.11+
from typing import Dict, Any, Optional, List  # version: 3.11+
import logging  # version: 3.11+

import numpy as np  # version: 1.24.0
from PIL import Image, ImageEnhance  # version: 10.0.0

from ocr.processors import OCRProcessor
from ocr.validators import OCRTaskConfigSchema
from core.exceptions import ValidationException

# Supported extraction types
EXTRACTION_TYPES = ["text", "table", "mixed"]

# Confidence thresholds for extraction validation
TABLE_CONFIDENCE_THRESHOLD = 0.90  # 90% confidence for table structure
TEXT_CONFIDENCE_THRESHOLD = 0.85   # 85% confidence for text content

# Configure logging
logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    """
    Abstract base class defining interface for OCR content extractors.
    
    Provides common functionality and interface definition for specialized
    content extraction implementations.
    """
    
    def __init__(self, config: OCRTaskConfigSchema) -> None:
        """
        Initialize base extractor with configuration.
        
        Args:
            config: Validated OCR task configuration
            
        Raises:
            ValidationException: If configuration is invalid
        """
        self._config = config
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Validate configuration
        if not config:
            raise ValidationException(
                "Missing required configuration",
                {"component": self.__class__.__name__}
            )
    
    @abstractmethod
    def extract(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract content from the provided image.
        
        Args:
            image: PIL Image object to process
            
        Returns:
            Dict[str, Any]: Extracted content and metadata
            
        Raises:
            ValidationException: If extraction fails
        """
        pass

class TextExtractor(BaseExtractor):
    """
    Specialized extractor for text-based content.
    
    Implements optimized text extraction with confidence validation
    and formatting capabilities.
    """
    
    def __init__(self, config: OCRTaskConfigSchema) -> None:
        """
        Initialize text extractor with configuration.
        
        Args:
            config: Validated OCR task configuration
            
        Raises:
            ValidationException: If configuration is invalid
        """
        super().__init__(config)
        self._processor = OCRProcessor(config)
        
        # Configure text-specific parameters
        self._min_confidence = TEXT_CONFIDENCE_THRESHOLD
        self._logger.info("Initialized text extractor with confidence threshold: %.2f", 
                         self._min_confidence)
    
    def extract(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract text content from image with validation.
        
        Args:
            image: PIL Image object to process
            
        Returns:
            Dict[str, Any]: Extracted text and confidence scores
            
        Raises:
            ValidationException: If extraction fails or confidence is too low
        """
        try:
            self._logger.debug("Starting text extraction for image %dx%d", 
                             image.width, image.height)
            
            # Extract text using OCR processor
            ocr_result = self._processor.extract_text(image)
            
            # Validate confidence
            if ocr_result.get('confidence', 0) < self._min_confidence * 100:
                raise ValidationException(
                    "Text extraction confidence below threshold",
                    {
                        "confidence": ocr_result.get('confidence'),
                        "threshold": self._min_confidence * 100
                    }
                )
            
            # Format and validate results
            result = {
                'content_type': 'text',
                'text': ocr_result['text'],
                'confidence': ocr_result['confidence'] / 100,
                'word_count': len(ocr_result['text'].split()),
                'metadata': {
                    'words': ocr_result['words'],
                    'boxes': ocr_result['boxes'],
                    'processing_options': self._config.processing_options
                }
            }
            
            self._logger.info("Text extraction completed with confidence: %.2f%%", 
                            result['confidence'] * 100)
            
            return result
            
        except Exception as e:
            self._logger.error("Text extraction failed: %s", str(e))
            raise ValidationException(
                "Text extraction failed",
                {"error": str(e)}
            )

class TableExtractor(BaseExtractor):
    """
    Specialized extractor for table-based content.
    
    Implements table structure detection and content extraction with
    grid-based analysis.
    """
    
    def __init__(self, config: OCRTaskConfigSchema) -> None:
        """
        Initialize table extractor with configuration.
        
        Args:
            config: Validated OCR task configuration
            
        Raises:
            ValidationException: If configuration is invalid
        """
        super().__init__(config)
        self._processor = OCRProcessor(config)
        self._min_confidence = TABLE_CONFIDENCE_THRESHOLD
        
        # Initialize table detection grid
        self._grid_detector = np.zeros((100, 100))  # Default grid size
        self._logger.info("Initialized table extractor with confidence threshold: %.2f", 
                         self._min_confidence)
    
    def extract(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract tabular content from image.
        
        Args:
            image: PIL Image object to process
            
        Returns:
            Dict[str, Any]: Extracted table structure and content
            
        Raises:
            ValidationException: If extraction fails or table structure invalid
        """
        try:
            self._logger.debug("Starting table extraction for image %dx%d", 
                             image.width, image.height)
            
            # Detect table structure
            grid_structure = self.detect_grid(image)
            
            # Extract cell contents
            cells_content = []
            for cell_coords in grid_structure:
                cell_image = self._extract_cell_image(image, cell_coords)
                cell_text = self._processor.extract_text(cell_image)
                cells_content.append({
                    'text': cell_text['text'],
                    'confidence': cell_text['confidence'] / 100,
                    'coordinates': cell_coords
                })
            
            # Validate table structure
            if not self._validate_table_structure(cells_content):
                raise ValidationException(
                    "Invalid table structure detected",
                    {"cell_count": len(cells_content)}
                )
            
            # Format results
            result = {
                'content_type': 'table',
                'structure': {
                    'rows': len(set(c['coordinates'][1] for c in cells_content)),
                    'columns': len(set(c['coordinates'][0] for c in cells_content))
                },
                'cells': cells_content,
                'confidence': sum(c['confidence'] for c in cells_content) / len(cells_content),
                'metadata': {
                    'grid_structure': grid_structure.tolist(),
                    'processing_options': self._config.processing_options
                }
            }
            
            self._logger.info("Table extraction completed with confidence: %.2f%%", 
                            result['confidence'] * 100)
            
            return result
            
        except Exception as e:
            self._logger.error("Table extraction failed: %s", str(e))
            raise ValidationException(
                "Table extraction failed",
                {"error": str(e)}
            )
    
    def detect_grid(self, image: Image.Image) -> np.ndarray:
        """
        Detect table grid structure in image.
        
        Args:
            image: PIL Image object to analyze
            
        Returns:
            np.ndarray: Detected grid structure coordinates
            
        Raises:
            ValidationException: If grid detection fails
        """
        try:
            # Convert to grayscale for edge detection
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast for better line detection
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Convert to numpy array for processing
            img_array = np.array(image)
            
            # Detect horizontal and vertical lines
            horizontal_lines = self._detect_lines(img_array, axis=0)
            vertical_lines = self._detect_lines(img_array, axis=1)
            
            # Find grid intersections
            grid = np.zeros_like(img_array)
            grid[horizontal_lines > 0] = 1
            grid[vertical_lines > 0] = 1
            
            # Extract cell coordinates
            return self._extract_cell_coordinates(grid)
            
        except Exception as e:
            raise ValidationException(
                "Grid detection failed",
                {"error": str(e)}
            )
    
    def _detect_lines(self, img_array: np.ndarray, axis: int) -> np.ndarray:
        """Helper method to detect lines in specified axis."""
        gradient = np.gradient(img_array, axis=axis)
        threshold = np.std(gradient) * 2
        return np.abs(gradient) > threshold
    
    def _extract_cell_coordinates(self, grid: np.ndarray) -> np.ndarray:
        """Helper method to extract cell coordinates from grid."""
        # Implementation would detect cells based on line intersections
        # Returning dummy coordinates for illustration
        return np.array([[0, 0, 100, 100]])
    
    def _extract_cell_image(self, image: Image.Image, coords: List[int]) -> Image.Image:
        """Helper method to extract cell image based on coordinates."""
        return image.crop(coords)
    
    def _validate_table_structure(self, cells_content: List[Dict[str, Any]]) -> bool:
        """Helper method to validate extracted table structure."""
        if not cells_content:
            return False
            
        # Check for minimum cell count
        if len(cells_content) < 4:  # Arbitrary minimum for illustration
            return False
            
        # Validate cell confidence scores
        cell_confidences = [cell['confidence'] for cell in cells_content]
        avg_confidence = sum(cell_confidences) / len(cell_confidences)
        
        return avg_confidence >= self._min_confidence

__all__ = [
    'BaseExtractor',
    'TextExtractor',
    'TableExtractor',
    'EXTRACTION_TYPES'
]