"""
Unit test suite for the command line interface implementation.

This module provides comprehensive testing of CLI commands including:
- Scraping task management
- OCR processing
- Status monitoring
- Configuration management

Version: 1.0.0
"""

import pytest  # version: 7.4+
from unittest.mock import patch, MagicMock  # version: 3.11+
from click.testing import CliRunner  # version: 8.1+
import json
import yaml
from pathlib import Path
from datetime import datetime

from src.cli.main import cli
from src.cli.commands.status import status_group
from src.cli.commands.config import CONFIG_GROUP
from src.cli.commands.ocr import OCR_COMMAND_GROUP
from src.cli.commands.scrape import scrape
from tests.utils.fixtures import create_test_task

@pytest.mark.unit
class TestCLI:
    """
    Comprehensive test suite for CLI command functionality.
    Tests all command groups with various inputs and edge cases.
    """

    def setup_method(self):
        """Initialize test environment before each test."""
        self.runner = CliRunner()
        self.test_config = {
            'source': 'https://test.com',
            'allowed_domains': ['test.com'],
            'rate_limit': {
                'requests_per_second': 1.0,
                'burst_size': 5
            }
        }

    def teardown_method(self):
        """Clean up test environment after each test."""
        pass

    @pytest.mark.unit
    @patch('src.services.scraping_service.ScrapingService')
    def test_scrape_start_command(self, mock_scraping_service):
        """Test scrape start command with various configurations."""
        # Setup mock service
        mock_service = MagicMock()
        mock_scraping_service.return_value = mock_service
        mock_service.validate_spider_health.return_value = True

        # Test with valid configuration file
        with self.runner.isolated_filesystem():
            config_path = Path('test_config.yaml')
            with open(config_path, 'w') as f:
                yaml.dump(self.test_config, f)

            result = self.runner.invoke(scrape, ['start', 'test-source', '-c', str(config_path)])
            assert result.exit_code == 0
            assert "Successfully" in result.output
            mock_service.validate_spider_health.assert_called_once()

        # Test without configuration file
        result = self.runner.invoke(scrape, ['start', 'test-source'])
        assert result.exit_code == 0

        # Test with invalid configuration
        with self.runner.isolated_filesystem():
            with open('invalid_config.yaml', 'w') as f:
                f.write("invalid: yaml: content")

            result = self.runner.invoke(scrape, ['start', 'test-source', '-c', 'invalid_config.yaml'])
            assert result.exit_code == 1
            assert "Error" in result.output

    @pytest.mark.unit
    @patch('src.services.ocr_service.OCRService')
    def test_ocr_process_command(self, mock_ocr_service):
        """Test OCR processing command functionality."""
        # Setup mock service
        mock_service = MagicMock()
        mock_ocr_service.return_value = mock_service
        mock_service.process_document.return_value = {
            'text': 'Test OCR result',
            'confidence': 0.95
        }

        # Test single file processing
        with self.runner.isolated_filesystem():
            # Create test PDF file
            test_file = Path('test.pdf')
            test_file.touch()

            result = self.runner.invoke(OCR_COMMAND_GROUP, [
                'process',
                str(test_file),
                '--output-dir', 'output',
                '--format', 'json'
            ])
            assert result.exit_code == 0
            assert "Successfully processed" in result.output

        # Test with invalid file
        result = self.runner.invoke(OCR_COMMAND_GROUP, [
            'process',
            'nonexistent.pdf'
        ])
        assert result.exit_code == 1
        assert "Error" in result.output

        # Test with invalid format
        with self.runner.isolated_filesystem():
            test_file = Path('test.txt')
            test_file.touch()
            result = self.runner.invoke(OCR_COMMAND_GROUP, [
                'process',
                str(test_file)
            ])
            assert result.exit_code == 1
            assert "Unsupported file type" in result.output

    @pytest.mark.unit
    @patch('src.services.task_service.TaskService')
    def test_status_tasks_command(self, mock_task_service):
        """Test status monitoring commands."""
        # Setup mock service
        mock_service = MagicMock()
        mock_task_service.return_value = mock_service
        
        # Create test tasks
        test_tasks = [
            create_test_task(
                task_type='scrape',
                status='running'
            ),
            create_test_task(
                task_type='ocr',
                status='completed'
            )
        ]
        mock_service.list_tasks.return_value = test_tasks

        # Test table format output
        result = self.runner.invoke(status_group, ['tasks', '--format', 'table'])
        assert result.exit_code == 0
        assert "Task ID" in result.output
        assert "Status" in result.output

        # Test JSON format output
        result = self.runner.invoke(status_group, ['tasks', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data['tasks']) == 2
        assert 'id' in data['tasks'][0]
        assert 'status' in data['tasks'][0]

        # Test with status filter
        result = self.runner.invoke(status_group, ['tasks', '--status', 'running'])
        assert result.exit_code == 0
        assert "running" in result.output

        # Test with metrics
        result = self.runner.invoke(status_group, ['tasks', '--show-metrics'])
        assert result.exit_code == 0
        assert "Metrics" in result.output

    @pytest.mark.unit
    @patch('src.services.config_service.ConfigService')
    def test_config_management(self, mock_config_service):
        """Test configuration management commands."""
        # Setup mock service
        mock_service = MagicMock()
        mock_config_service.return_value = mock_service

        test_config = {
            'api': {
                'timeout': 30,
                'rate_limit': {
                    'max_requests': 1000,
                    'window_size': 3600
                }
            },
            'storage': {
                'retention': {
                    'days': 90
                },
                'encryption': {
                    'enabled': True
                }
            }
        }
        mock_service.get_config.return_value = test_config

        # Test view command
        result = self.runner.invoke(CONFIG_GROUP, ['view'])
        assert result.exit_code == 0
        assert "api" in result.output
        assert "storage" in result.output

        # Test view with format option
        result = self.runner.invoke(CONFIG_GROUP, ['view', '--format', 'yaml'])
        assert result.exit_code == 0
        assert "api:" in result.output

        # Test set command
        result = self.runner.invoke(CONFIG_GROUP, [
            'set',
            'api.timeout',
            '60',
            '--force'
        ])
        assert result.exit_code == 0
        assert "Successfully updated" in result.output

        # Test validate command
        with self.runner.isolated_filesystem():
            config_file = Path('test_config.yaml')
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)

            result = self.runner.invoke(CONFIG_GROUP, [
                'validate',
                '--config-file', str(config_file),
                '--env', 'prod'
            ])
            assert result.exit_code == 0
            assert "Validation Results" in result.output

        # Test invalid configuration
        result = self.runner.invoke(CONFIG_GROUP, [
            'set',
            'invalid.key',
            'value'
        ])
        assert result.exit_code == 1
        assert "Error" in result.output