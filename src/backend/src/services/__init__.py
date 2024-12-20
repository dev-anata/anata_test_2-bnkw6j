"""
Service layer initialization module exposing core service classes.

This module provides a clean interface for accessing service layer functionality
throughout the application, including task processing, data management, OCR processing,
web scraping, and storage operations.

Version: 1.0.0
"""

from services.storage_service import StorageService
from services.data_service import DataService
from services.ocr_service import OCRService
from services.scraping_service import ScrapingService
from services.task_service import TaskService

# Export core service classes
__all__ = [
    'StorageService',  # Storage operations service
    'DataService',     # Data management service
    'OCRService',      # OCR processing service
    'ScrapingService', # Web scraping service
    'TaskService'      # Task management service
]