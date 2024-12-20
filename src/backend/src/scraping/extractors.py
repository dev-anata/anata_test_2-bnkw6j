"""
Content extraction module for web scraping operations.

This module provides robust and validated content extraction capabilities for different
types of web content including text, tables, and structured data. It implements
comprehensive validation and accuracy features to ensure high-quality data extraction.

Version: 1.0.0
"""

from typing import Dict, Any, Optional, Tuple, List, Union  # version: 3.11+
import unicodedata  # version: 3.11+
import re  # version: 3.11+
import logging  # version: 3.11+
from bs4 import BeautifulSoup  # version: 4.12+
import pandas as pd  # version: 2.0+
from lxml import etree  # version: 4.9+

from core.types import TaskResult
from core.models import DataObject
from scraping.settings import scraping_settings
from core.exceptions import ValidationException

# Configure logging
logger = logging.getLogger(__name__)

class BaseExtractor:
    """
    Enhanced base class for content extraction with comprehensive validation.
    
    Provides core functionality for HTML parsing, text cleaning, and content validation
    with support for configurable validation rules and error handling.
    """
    
    def __init__(self, html_content: str, config: Dict[str, Any], 
                 validation_rules: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize base extractor with validation rules.
        
        Args:
            html_content: Raw HTML content to process
            config: Extraction configuration parameters
            validation_rules: Optional validation rules for content
        
        Raises:
            ValidationException: If HTML content is invalid or empty
        """
        if not html_content:
            raise ValidationException("Empty HTML content", {"error": "content_empty"})
        
        self.soup = BeautifulSoup(html_content, 'lxml')
        self.config = config
        self.validation_rules = validation_rules or {}
        
        # Default validation settings
        self.min_content_length = self.validation_rules.get('min_length', 1)
        self.max_content_length = self.validation_rules.get('max_length', 100000)
        self.allowed_tags = self.validation_rules.get('allowed_tags', 
                                                    ['p', 'span', 'div', 'table'])
        
    def clean_text(self, text: str) -> str:
        """
        Enhanced text cleaning with unicode normalization and special character handling.
        
        Args:
            text: Raw text content to clean
        
        Returns:
            Cleaned and normalized text string
        """
        if not text:
            return ""
        
        # Normalize unicode characters
        text = unicodedata.normalize('NFKC', text)
        
        # Remove HTML entities
        text = re.sub(r'&[a-zA-Z]+;', ' ', text)
        
        # Remove control characters
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C')
        
        # Standardize whitespace
        text = ' '.join(text.split())
        
        # Handle special characters
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        
        return text.strip()
    
    def validate_content(self, content: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """
        Validate extracted content against defined rules.
        
        Args:
            content: Extracted content to validate
            rules: Validation rules to apply
            
        Returns:
            bool: True if content passes validation, False otherwise
            
        Raises:
            ValidationException: If content fails validation
        """
        if not content:
            raise ValidationException("Empty content", {"error": "content_empty"})
            
        # Check content length
        content_length = len(str(content))
        if content_length < self.min_content_length:
            raise ValidationException(
                "Content too short",
                {"length": content_length, "min_required": self.min_content_length}
            )
            
        if content_length > self.max_content_length:
            raise ValidationException(
                "Content too long",
                {"length": content_length, "max_allowed": self.max_content_length}
            )
            
        # Validate data formats
        for field, value in content.items():
            field_type = rules.get(field, {}).get('type')
            if field_type and not isinstance(value, field_type):
                raise ValidationException(
                    f"Invalid type for field {field}",
                    {"expected": field_type.__name__, "received": type(value).__name__}
                )
        
        return True

class TableExtractor(BaseExtractor):
    """
    Enhanced table data extractor with comprehensive validation.
    
    Specializes in extracting and validating tabular data with support for
    complex table structures and data type validation.
    """
    
    def __init__(self, html_content: str, config: Dict[str, Any],
                 validation_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize table extractor with validation settings.
        
        Args:
            html_content: Raw HTML content containing tables
            config: Extraction configuration
            validation_config: Optional table-specific validation rules
        """
        super().__init__(html_content, config, validation_config)
        
        self.table_selector = config.get('table_selector', 'table')
        self.validation_config = validation_config or {}
        
        # Configure pandas display settings
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_rows', None)
        
    def extract(self) -> Dict[str, Any]:
        """
        Extract and validate tabular data.
        
        Returns:
            Dict containing validated table data
            
        Raises:
            ValidationException: If table extraction or validation fails
        """
        tables = self.soup.select(self.table_selector)
        if not tables:
            raise ValidationException(
                "No tables found",
                {"selector": self.table_selector}
            )
            
        extracted_tables = []
        for idx, table in enumerate(tables):
            try:
                # Convert to pandas DataFrame
                df = pd.read_html(str(table))[0]
                
                # Clean column names
                df.columns = [self.clean_text(str(col)) for col in df.columns]
                
                # Clean cell contents
                for col in df.columns:
                    df[col] = df[col].apply(
                        lambda x: self.clean_text(str(x)) if pd.notna(x) else None
                    )
                
                # Validate table structure
                validation_result, message = self.validate_table(df)
                if not validation_result:
                    logger.warning(f"Table {idx} validation failed: {message}")
                    continue
                
                extracted_tables.append(df.to_dict('records'))
                
            except Exception as e:
                logger.error(f"Error processing table {idx}: {str(e)}")
                continue
        
        return {
            "tables": extracted_tables,
            "count": len(extracted_tables),
            "metadata": {
                "extractor": "TableExtractor",
                "selector": self.table_selector,
                "validation_rules": self.validation_config
            }
        }
    
    def validate_table(self, table: pd.DataFrame) -> Tuple[bool, str]:
        """
        Comprehensive table validation.
        
        Args:
            table: Pandas DataFrame to validate
            
        Returns:
            Tuple of (validation_success, error_message)
        """
        # Check dimensions
        min_rows = self.validation_config.get('min_rows', 1)
        max_rows = self.validation_config.get('max_rows', 10000)
        
        if len(table) < min_rows:
            return False, f"Table has fewer than {min_rows} rows"
        
        if len(table) > max_rows:
            return False, f"Table exceeds {max_rows} rows"
        
        # Validate column names
        if table.columns.duplicated().any():
            return False, "Duplicate column names found"
        
        # Check for empty columns
        empty_cols = table.columns[table.isna().all()].tolist()
        if empty_cols:
            return False, f"Empty columns found: {empty_cols}"
        
        # Check data consistency
        for col in table.columns:
            # Check for mixed data types
            non_null_values = table[col].dropna()
            if len(non_null_values) > 0:
                first_type = type(non_null_values.iloc[0])
                if not all(isinstance(x, first_type) for x in non_null_values):
                    return False, f"Mixed data types in column: {col}"
        
        return True, "Validation successful"

__all__ = [
    'BaseExtractor',
    'TableExtractor'
]