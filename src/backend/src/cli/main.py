"""
Main entry point for the Data Processing Pipeline CLI application.

This module implements the core CLI structure with enterprise-grade features including:
- Command groups for scraping, OCR, status, and configuration management
- Enhanced security controls and input validation
- Comprehensive error handling and logging
- Performance monitoring and telemetry
- Rich formatting and progress tracking

Version: 1.0.0
"""

import sys  # version: 3.11+
import click  # version: 8.1+
from rich.console import Console  # version: 13.0+
import structlog  # version: 23.1+
from typing import Optional, Dict, Any  # version: 3.11+

from cli.commands.status import status_group
from cli.commands.config import CONFIG_GROUP
from cli.commands.ocr import OCR_COMMAND_GROUP
from cli.commands.scrape import scrape

# Initialize rich console for enhanced output
console = Console()

# Initialize structured logger
logger = structlog.get_logger(__name__)

@click.group()
@click.version_option(version='1.0.0')
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    Data Processing Pipeline CLI - Enterprise-grade data processing automation.

    Features:
    - Web scraping with rate limiting and security controls
    - OCR processing with quality validation
    - Status monitoring and metrics collection
    - Configuration management with validation
    """
    # Initialize CLI context
    ctx.ensure_object(dict)
    
    # Configure telemetry collection
    ctx.obj['start_time'] = time.time()
    ctx.obj['command_path'] = ctx.command_path
    
    # Initialize security context
    ctx.obj['security_context'] = {
        'environment': settings.env,
        'debug_mode': settings.debug
    }
    
    logger.info(
        "CLI session started",
        extra={
            "command_path": ctx.command_path,
            "environment": settings.env
        }
    )

def main() -> int:
    """
    Main entry point for the CLI application with enhanced error handling.

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    try:
        # Configure structured logging
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            wrapper_class=structlog.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Register command groups
        cli.add_command(status_group)
        cli.add_command(CONFIG_GROUP)
        cli.add_command(OCR_COMMAND_GROUP)
        cli.add_command(scrape)

        # Configure command aliases for convenience
        cli.add_command(status_group, name='st')
        cli.add_command(CONFIG_GROUP, name='cfg')
        
        # Set up exception handlers
        def handle_error(error: Exception) -> None:
            """Handle uncaught exceptions with proper logging."""
            logger.error(
                "Command failed",
                exc=error,
                extra={"error_type": type(error).__name__}
            )
            console.print(f"[red]Error: {str(error)}[/red]")
            if settings.debug:
                console.print_exception()

        # Run CLI with error handling
        try:
            cli(standalone_mode=False)
            return 0
        except click.ClickException as e:
            e.show()
            return e.exit_code
        except click.Abort:
            console.print("\n[yellow]Operation cancelled[/yellow]")
            return 1
        except Exception as e:
            handle_error(e)
            return 1
        finally:
            # Perform cleanup
            logger.info("CLI session ended")

    except Exception as e:
        console.print(f"[red]Fatal error: {str(e)}[/red]")
        if settings.debug:
            console.print_exception()
        return 1

if __name__ == '__main__':
    sys.exit(main())