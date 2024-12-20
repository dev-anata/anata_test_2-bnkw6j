"""
Command line interface initialization module for the Data Processing Pipeline.

This module exports the main CLI application and version information, providing
centralized access to CLI functionality while maintaining clean dependency structure.

Version: 1.0.0
"""

import click  # version: 8.1+

from cli.main import cli

# Package version following semantic versioning
__version__ = '1.0.0'

# Export main CLI application group
__all__ = ['cli', '__version__']