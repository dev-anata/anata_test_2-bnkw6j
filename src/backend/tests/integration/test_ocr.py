"""
Integration tests for OCR processing functionality.

This module provides comprehensive integration testing for the OCR processing pipeline,
validating end-to-end document processing, accuracy requirements, and performance SLAs.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
import pytest  # version: 7.4+
from unittest.mock import Mock, patch  # version: 3.11+
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from typing import Dict, Any, List

from ocr.engine import OCREngine
from ocr.processors import OCRProcessor
from services.ocr_service import OCRService
from storage.cloud_storage import CloudStorageBackend
from core.exceptions import ValidationException, StorageException
from tests.utils.fixtures import (
    create_test_task,
    create_test_execution,
    create_test_data_object
)

@pytest.mark.integration
class TestOCRIntegration:
    """
    Integration test suite for OCR functionality with comprehensive test coverage.
    
    Tests end-to-end OCR processing including accuracy validation, performance
    benchmarking, and error handling scenarios.
    """

    def setup_method(self):
        """Set up test environment before each test."""
        # Initialize mock storage backend
        self._storage_client = Mock(spec=CloudStorageBackend)
        
        # Configure test OCR service
        self._test_config = {
            'timeout_seconds': 300,
            'max_retries': 3,
            'quality_threshold': 0.98,
            'memory_limit_mb': 2048
        }
        
        self._ocr_service = OCRService(
            storage_backend=self._storage_client,
            config=self._test_config
        )
        
        # Initialize performance metrics
        self._metrics = {
            'processing_times': [],
            'accuracy_scores': [],
            'memory_usage': []
        }

    def teardown_method(self):
        """Clean up test environment after each test."""
        # Clean up temporary files
        for temp_file in getattr(self, '_temp_files', []):
            try:
                Path(temp_file).unlink(missing_ok=True)
            except Exception as e:
                print(f"Failed to clean up {temp_file}: {e}")
        
        # Reset mock storage
        self._storage_client.reset_mock()
        
        # Clear metrics
        self._metrics = {
            'processing_times': [],
            'accuracy_scores': [],
            'memory_usage': []
        }

    @pytest.mark.asyncio
    async def test_ocr_engine_initialization(self):
        """Test OCR engine initialization with various configurations."""
        # Test default configuration
        config = {
            'source_path': 'test.pdf',
            'output_format': 'json',
            'languages': ['eng'],
            'processing_options': {},
            'timeout_seconds': 300,
            'enable_preprocessing': True
        }
        
        engine = OCREngine(config)
        assert engine is not None
        
        # Verify engine properties
        metrics = engine.get_performance_metrics()
        assert metrics['metrics']['total_tasks'] == 0
        assert metrics['metrics']['peak_memory_usage'] >= 0
        
        # Test invalid configuration
        with pytest.raises(ValidationException):
            invalid_config = config.copy()
            invalid_config['languages'] = ['invalid']
            OCREngine(invalid_config)

    @pytest.mark.asyncio
    async def test_ocr_document_processing(self):
        """Test end-to-end document processing workflow."""
        # Create test document
        test_content = "Test OCR Content\nLine 2\nLine 3"
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(test_content.encode())
            self._temp_files = getattr(self, '_temp_files', []) + [temp_file.name]
        
        # Create test task
        task = await create_test_task(
            task_type="ocr",
            config={
                'source_path': temp_file.name,
                'output_format': 'json',
                'languages': ['eng'],
                'processing_options': {
                    'dpi': 300,
                    'preprocessing': True
                }
            }
        )
        
        # Configure storage mock
        self._storage_client.retrieve_object.return_value = \
            Mock(read=Mock(return_value=test_content.encode()))
        
        # Process document
        start_time = datetime.utcnow()
        result = await self._ocr_service.process(task.configuration)
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify processing time SLA
        assert processing_time < 300, "Processing exceeded 5-minute SLA"
        
        # Verify accuracy requirement
        assert result['metadata']['quality_score'] >= 0.98, \
            "OCR accuracy below 98% requirement"
        
        # Verify storage operations
        self._storage_client.store_object.assert_called_once()
        stored_data = self._storage_client.store_object.call_args[1]
        assert stored_data['metadata']['content_type'] == 'text/plain'
        assert stored_data['metadata']['confidence'] >= 98.0

    @pytest.mark.asyncio
    async def test_ocr_error_handling(self):
        """Test OCR error scenarios and recovery mechanisms."""
        # Test invalid document format
        with pytest.raises(ValidationException) as exc_info:
            await self._ocr_service.process({
                'source_path': 'invalid.xyz',
                'output_format': 'json'
            })
        assert "Unsupported file format" in str(exc_info.value)
        
        # Test storage errors
        self._storage_client.retrieve_object.side_effect = StorageException(
            "Storage error",
            "test_path",
            {"error": "Access denied"}
        )
        
        with pytest.raises(StorageException):
            await self._ocr_service.process({
                'source_path': 'test.pdf',
                'output_format': 'json'
            })
        
        # Test timeout handling
        with patch('asyncio.sleep', side_effect=asyncio.TimeoutError):
            with pytest.raises(ValidationException) as exc_info:
                await self._ocr_service.process({
                    'source_path': 'test.pdf',
                    'output_format': 'json',
                    'timeout_seconds': 1
                })
            assert "OCR processing timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ocr_concurrent_processing(self):
        """Test concurrent OCR processing capabilities."""
        # Create multiple test documents
        test_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(f"Test content {i}".encode())
                test_files.append(temp_file.name)
                self._temp_files = getattr(self, '_temp_files', []) + [temp_file.name]
        
        # Configure storage mock
        self._storage_client.retrieve_object.return_value = \
            Mock(read=Mock(return_value=b"Test content"))
        
        # Process documents concurrently
        tasks = []
        for file_path in test_files:
            task = await create_test_task(
                task_type="ocr",
                config={
                    'source_path': file_path,
                    'output_format': 'json'
                }
            )
            tasks.append(self._ocr_service.process(task.configuration))
        
        # Wait for all tasks to complete
        start_time = datetime.utcnow()
        results = await asyncio.gather(*tasks)
        total_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify results
        assert len(results) == len(test_files)
        for result in results:
            assert result['status'] == 'completed'
            assert result['metadata']['quality_score'] >= 0.98
        
        # Verify concurrent processing performance
        assert total_time < 300 * len(test_files), \
            "Concurrent processing exceeded cumulative SLA"
        
        # Verify resource management
        metrics = self._ocr_service.get_performance_metrics()
        assert metrics['task_counts']['total'] == len(test_files)
        assert metrics['task_counts']['failed'] == 0