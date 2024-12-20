"""
Command line interface implementation for web scraping operations.

This module implements CLI commands for managing web scraping tasks with:
- Rich progress tracking and formatting
- Comprehensive error handling
- Multiple output formats
- Detailed logging
- Task validation

Version: 1.0.0
"""

import sys  # version: 3.11+
import click  # version: 8.1+
import yaml  # version: 6.0+
from typing import Optional, Dict, Any  # version: 3.11+
from rich.console import Console  # version: 13.0+
from rich.table import Table  # version: 13.0+
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID  # version: 13.0+
from rich.panel import Panel  # version: 13.0+

from services.scraping_service import ScrapingService
from tasks.scraping_tasks import ScrapingTask, ScrapingTaskExecutor
from scraping.settings import scraping_settings
from monitoring.logger import get_logger

# Initialize rich console and logger
console = Console()
logger = get_logger(__name__)

@click.group(name='scrape')
def scrape() -> None:
    """
    Manage web scraping operations with enhanced progress tracking.
    
    Provides commands for starting, stopping, and listing scraping tasks
    with rich formatting and comprehensive status updates.
    """
    pass

@scrape.command(name='start')
@click.argument('source_id')
@click.option('--config-file', '-c', type=click.Path(exists=True), help='YAML configuration file')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']), default='INFO')
def start(source_id: str, config_file: Optional[str], log_level: str) -> None:
    """
    Start a new scraping task with progress tracking.

    Args:
        source_id: Identifier for the data source
        config_file: Optional YAML configuration file
        log_level: Logging level for the task
    """
    try:
        # Load configuration
        config = {}
        if config_file:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)

        # Add source ID to config
        config['source'] = source_id
        
        # Initialize services
        scraping_service = ScrapingService()
        
        # Validate spider health
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task_id = progress.add_task("Validating spider health...", total=None)
            health_status = scraping_service.validate_spider_health(source_id)
            
            if not health_status:
                console.print(Panel(
                    "[red]Spider health check failed[/red]",
                    title="Error"
                ))
                sys.exit(1)
            
            progress.update(task_id, completed=True)

        # Create and validate task
        task = ScrapingTask(config)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            # Initialize progress tracking
            progress_id = progress.add_task("Starting scraping task...", total=100)
            
            # Execute task with progress updates
            try:
                executor = ScrapingTaskExecutor(task)
                result = executor.execute(config)
                
                # Update progress based on task status
                while not result.is_complete():
                    status = result.get_status()
                    progress.update(
                        progress_id,
                        completed=status.progress * 100,
                        description=f"Scraping: {status.current_action}"
                    )
                    
                # Show completion status
                if result.is_successful():
                    console.print(Panel(
                        f"[green]Successfully scraped {result.items_scraped} items[/green]",
                        title="Success"
                    ))
                else:
                    console.print(Panel(
                        f"[yellow]Task completed with warnings: {result.warnings}[/yellow]",
                        title="Warning"
                    ))
                    
            except Exception as e:
                console.print(Panel(
                    f"[red]Task failed: {str(e)}[/red]",
                    title="Error"
                ))
                logger.error("Scraping task failed", exc=e, extra={"source_id": source_id})
                sys.exit(1)

    except Exception as e:
        console.print(Panel(
            f"[red]Failed to start task: {str(e)}[/red]",
            title="Error"
        ))
        logger.error("Failed to start scraping task", exc=e)
        sys.exit(1)

@scrape.command(name='stop')
@click.argument('task_id')
def stop(task_id: str) -> None:
    """
    Stop a running scraping task.

    Args:
        task_id: ID of the task to stop
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress_id = progress.add_task("Stopping task...", total=None)
            
            # Initialize task executor
            executor = ScrapingTaskExecutor()
            
            # Stop task
            result = executor.stop(task_id)
            
            if result:
                console.print(Panel(
                    "[green]Task stopped successfully[/green]",
                    title="Success"
                ))
            else:
                console.print(Panel(
                    "[yellow]Task not found or already stopped[/yellow]",
                    title="Warning"
                ))
                
            progress.update(progress_id, completed=True)
            
    except Exception as e:
        console.print(Panel(
            f"[red]Failed to stop task: {str(e)}[/red]",
            title="Error"
        ))
        logger.error("Failed to stop task", exc=e, extra={"task_id": task_id})
        sys.exit(1)

@scrape.command(name='list')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml']), default='table')
@click.option('--details', '-d', is_flag=True, help='Show detailed task information')
def list_tasks(format: str, details: bool) -> None:
    """
    List all scraping tasks with rich formatting.

    Args:
        format: Output format (table, json, yaml)
        details: Show detailed task information
    """
    try:
        # Get task list
        executor = ScrapingTaskExecutor()
        tasks = executor.list_tasks()
        
        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return
            
        if format == 'table':
            # Create rich table
            table = Table(title="Scraping Tasks")
            
            # Add columns
            table.add_column("Task ID", style="cyan")
            table.add_column("Source", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Progress", style="blue")
            if details:
                table.add_column("Start Time", style="magenta")
                table.add_column("Items Scraped", style="green")
                table.add_column("Errors", style="red")
            
            # Add rows
            for task in tasks:
                row = [
                    task.id,
                    task.source,
                    task.status,
                    f"{task.progress:.1f}%"
                ]
                if details:
                    row.extend([
                        task.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        str(task.items_scraped),
                        str(len(task.errors))
                    ])
                table.add_row(*row)
            
            console.print(table)
            
        elif format == 'json':
            import json
            console.print_json(json.dumps([task.to_dict() for task in tasks]))
            
        elif format == 'yaml':
            console.print(yaml.dump([task.to_dict() for task in tasks]))
            
    except Exception as e:
        console.print(Panel(
            f"[red]Failed to list tasks: {str(e)}[/red]",
            title="Error"
        ))
        logger.error("Failed to list tasks", exc=e)
        sys.exit(1)

if __name__ == '__main__':
    scrape()