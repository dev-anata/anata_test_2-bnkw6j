"""
Command line interface initialization module for the data processing pipeline.

This module aggregates and validates all CLI command groups (scrape, ocr, status, config)
with comprehensive error handling and validation. It provides centralized command
registration and validation to ensure consistent CLI behavior.

Version: 1.0.0
"""

import click  # version: 8.1+
import structlog  # version: 23.1+
from typing import Optional, Dict, Any

from cli.commands.status import status_group
from cli.commands.config import CONFIG_GROUP
from cli.commands.ocr import OCR_COMMAND_GROUP
from cli.commands.scrape import scrape
from core.exceptions import ValidationException

# Initialize structured logger
logger = structlog.get_logger(__name__)

def validate_command_group(command_group: click.Group, group_name: str) -> bool:
    """
    Validate a command group before registration with comprehensive checks.

    Args:
        command_group: Click command group to validate
        group_name: Name of the command group for logging

    Returns:
        bool: True if validation passes, False otherwise

    Raises:
        ValidationException: If command group validation fails
    """
    try:
        # Validate command group type
        if not isinstance(command_group, click.Group):
            raise ValidationException(
                "Invalid command group type",
                {"expected": "click.Group", "received": type(command_group).__name__}
            )

        # Validate command group has required attributes
        required_attrs = ['name', 'commands', 'params']
        for attr in required_attrs:
            if not hasattr(command_group, attr):
                raise ValidationException(
                    f"Command group missing required attribute: {attr}",
                    {"group_name": group_name}
                )

        # Validate command group has at least one command
        if not command_group.commands:
            raise ValidationException(
                "Command group has no commands",
                {"group_name": group_name}
            )

        # Validate command names
        for cmd_name, cmd in command_group.commands.items():
            if not isinstance(cmd_name, str) or not cmd_name:
                raise ValidationException(
                    "Invalid command name",
                    {"group_name": group_name, "command_name": cmd_name}
                )

        logger.debug(
            "Command group validation successful",
            group_name=group_name,
            command_count=len(command_group.commands)
        )
        return True

    except Exception as e:
        logger.error(
            "Command group validation failed",
            error=str(e),
            group_name=group_name
        )
        return False

def register_commands(cli_app: click.Group) -> None:
    """
    Register all command groups with the main CLI application.

    Performs validation and error handling during registration to ensure
    all commands are properly configured and accessible.

    Args:
        cli_app: Main Click CLI application instance

    Raises:
        ValidationException: If command registration fails
    """
    try:
        # Validate CLI app
        if not isinstance(cli_app, click.Group):
            raise ValidationException(
                "Invalid CLI application type",
                {"expected": "click.Group", "received": type(cli_app).__name__}
            )

        # Define command groups with validation
        command_groups = {
            'status': status_group,
            'config': CONFIG_GROUP,
            'ocr': OCR_COMMAND_GROUP,
            'scrape': scrape
        }

        # Register each command group with validation
        for group_name, command_group in command_groups.items():
            try:
                # Validate command group
                if validate_command_group(command_group, group_name):
                    # Add command group to CLI
                    cli_app.add_command(command_group)
                    logger.info(
                        "Registered command group",
                        group_name=group_name,
                        commands=list(command_group.commands.keys())
                    )
                else:
                    logger.error(
                        "Skipping invalid command group",
                        group_name=group_name
                    )

            except Exception as e:
                logger.error(
                    "Failed to register command group",
                    error=str(e),
                    group_name=group_name
                )
                # Continue with other command groups
                continue

        logger.info(
            "Command registration complete",
            registered_groups=list(command_groups.keys())
        )

    except Exception as e:
        logger.error("Command registration failed", error=str(e))
        raise ValidationException(
            "Failed to register CLI commands",
            {"error": str(e)}
        )

# Export command groups for CLI registration
__all__ = [
    'status_group',
    'CONFIG_GROUP',
    'OCR_COMMAND_GROUP',
    'scrape',
    'register_commands'
]