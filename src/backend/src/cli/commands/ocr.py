"""
OCR command line interface module providing commands for OCR operations.

This module implements the OCR command group with comprehensive functionality for
processing documents, checking task status, and managing batch processing with
enhanced error handling and progress tracking.

Version: 1.0.0
"""

import asyncio  # version: 3.11+
from pathlib import Path  # version: 3.11+
from typing import List, Optional, Dict, Any  # version: 3.11+
import sys
import time

import click  # version: 8.1.0
from rich.console import Console  # version: 13.0.0
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn  # version: 13.0.0
from rich.table import Table  # version: 13.0.0

from ocr.engine import OCREngine
from ocr.validators import (
    OCRTaskConfigSchema,
    validate_ocr_task,
    SUPPORTED_FORMATS,
    DEFAULT_PROCESSING_OPTIONS
)
from services.ocr_service import OCRService
from core.exceptions import ValidationException

# Initialize rich console for enhanced output
console = Console()

# Constants
SUPPORTED_FILE_TYPES = SUPPORTED_FORMATS
DEFAULT_OUTPUT_FORMAT = 'json'
MAX_BATCH_SIZE = 100

@click.group(name='ocr', help='OCR processing commands with enhanced error handling and progress tracking')
def OCR_COMMAND_GROUP():
    """OCR command group for document processing operations."""
    pass

@OCR_COMMAND_GROUP.command(name='process', help='Process a document using OCR with progress tracking')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory for results')
@click.option('--format', '-f', type=click.Choice(['json', 'text']), default='json', help='Output format')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--language', '-l', multiple=True, help='OCR language(s) to use (e.g., eng, fra)')
@click.option('--quality-threshold', type=float, default=0.85, help='Minimum quality threshold (0-1)')
def process_command(
    file_path: str,
    output_dir: Optional[str],
    format: str,
    verbose: bool,
    language: tuple,
    quality_threshold: float
) -> None:
    """
    Process a single document using OCR with enhanced progress tracking.

    Args:
        file_path: Path to the document to process
        output_dir: Optional output directory for results
        format: Output format (json or text)
        verbose: Enable verbose output
        language: OCR language(s) to use
        quality_threshold: Minimum quality threshold
    """
    try:
        # Validate input file
        input_path = Path(file_path)
        if input_path.suffix.lower() not in SUPPORTED_FILE_TYPES:
            raise ValidationException(
                "Unsupported file type",
                {"supported_formats": list(SUPPORTED_FILE_TYPES)}
            )

        # Validate/create output directory
        output_path = Path(output_dir) if output_dir else input_path.parent / 'ocr_output'
        output_path.mkdir(parents=True, exist_ok=True)

        # Prepare OCR configuration
        config = {
            'source_path': str(input_path),
            'output_format': format,
            'languages': list(language) if language else ['eng'],
            'processing_options': {
                **DEFAULT_PROCESSING_OPTIONS,
                'quality_threshold': quality_threshold
            },
            'enable_preprocessing': True
        }

        # Validate configuration
        validated_config = validate_ocr_task(config)
        config_schema = OCRTaskConfigSchema(**validated_config)

        # Initialize OCR engine
        engine = OCREngine(config_schema)

        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            # Create processing task
            task = progress.add_task(
                f"Processing {input_path.name}",
                total=100
            )

            # Process document with progress updates
            try:
                result = asyncio.run(engine.async_process_document(
                    task_id=str(input_path.name),
                    extraction_type='text'
                ))

                # Update progress
                progress.update(task, completed=100)

                # Save results
                output_file = output_path / f"{input_path.stem}_ocr.{format}"
                if format == 'json':
                    import json
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2)
                else:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result['text'])

                # Display success message with metrics
                console.print(f"\n[green]Successfully processed {input_path.name}[/green]")
                
                if verbose:
                    metrics_table = Table(title="Processing Metrics")
                    metrics_table.add_column("Metric", style="cyan")
                    metrics_table.add_column("Value", style="magenta")
                    
                    metrics_table.add_row("Confidence", f"{result['confidence']:.2f}%")
                    metrics_table.add_row("Processing Time", f"{result['processing_time']:.2f}s")
                    metrics_table.add_row("Word Count", str(len(result['text'].split())))
                    
                    console.print(metrics_table)

            except Exception as e:
                progress.update(task, completed=0, description=f"[red]Failed: {str(e)}[/red]")
                raise

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)

@OCR_COMMAND_GROUP.command(name='status', help='Check OCR task status with detailed progress')
@click.argument('task_id', required=False)
@click.option('--watch', '-w', is_flag=True, help='Watch task progress in real-time')
@click.option('--interval', type=int, default=5, help='Status update interval in seconds')
def status_command(task_id: Optional[str], watch: bool, interval: int) -> None:
    """
    Check status of OCR processing tasks with detailed progress information.

    Args:
        task_id: Optional specific task ID to check
        watch: Enable real-time status monitoring
        interval: Status update interval in seconds
    """
    try:
        # Initialize OCR service
        service = OCRService()

        def display_status(metrics: Dict[str, Any]) -> None:
            """Helper function to display status information."""
            status_table = Table(title="OCR Processing Status")
            status_table.add_column("Metric", style="cyan")
            status_table.add_column("Value", style="magenta")

            for category, values in metrics.items():
                if isinstance(values, dict):
                    for key, value in values.items():
                        status_table.add_row(
                            f"{category.replace('_', ' ').title()} - {key.replace('_', ' ').title()}",
                            f"{value:.2f}" if isinstance(value, float) else str(value)
                        )
                else:
                    status_table.add_row(
                        category.replace('_', ' ').title(),
                        f"{values:.2f}" if isinstance(values, float) else str(values)
                    )

            console.clear()
            console.print(status_table)

        if watch:
            try:
                while True:
                    metrics = service.get_performance_metrics()
                    display_status(metrics)
                    time.sleep(interval)
            except KeyboardInterrupt:
                console.print("\n[yellow]Status monitoring stopped[/yellow]")
        else:
            metrics = service.get_performance_metrics()
            display_status(metrics)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)

@OCR_COMMAND_GROUP.command(name='batch', help='Process multiple documents in batch with parallel processing')
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory for results')
@click.option('--format', '-f', type=click.Choice(['json', 'text']), default='json', help='Output format')
@click.option('--workers', '-w', type=int, default=4, help='Number of parallel workers')
@click.option('--recursive', '-r', is_flag=True, help='Process directories recursively')
def batch_command(
    input_dir: str,
    output_dir: Optional[str],
    format: str,
    workers: int,
    recursive: bool
) -> None:
    """
    Process multiple documents in batch mode with parallel processing.

    Args:
        input_dir: Input directory containing documents
        output_dir: Optional output directory for results
        format: Output format (json or text)
        workers: Number of parallel workers
        recursive: Process directories recursively
    """
    try:
        # Collect all supported files
        input_path = Path(input_dir)
        pattern = '**/*' if recursive else '*'
        files = [
            f for f in input_path.glob(pattern)
            if f.is_file() and f.suffix.lower() in SUPPORTED_FILE_TYPES
        ]

        if not files:
            console.print("[yellow]No supported files found for processing[/yellow]")
            return

        if len(files) > MAX_BATCH_SIZE:
            raise ValidationException(
                "Batch size exceeds maximum limit",
                {"max_size": MAX_BATCH_SIZE, "found": len(files)}
            )

        # Prepare output directory
        output_path = Path(output_dir) if output_dir else input_path / 'ocr_output'
        output_path.mkdir(parents=True, exist_ok=True)

        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            # Create overall progress task
            main_task = progress.add_task(
                f"Processing {len(files)} files",
                total=len(files)
            )

            # Process files in parallel
            async def process_batch():
                semaphore = asyncio.Semaphore(workers)
                tasks = []

                async def process_file(file_path: Path):
                    async with semaphore:
                        try:
                            # Prepare configuration
                            config = {
                                'source_path': str(file_path),
                                'output_format': format,
                                'enable_preprocessing': True
                            }
                            validated_config = validate_ocr_task(config)
                            config_schema = OCRTaskConfigSchema(**validated_config)

                            # Process document
                            engine = OCREngine(config_schema)
                            result = await engine.async_process_document(
                                task_id=str(file_path.name),
                                extraction_type='text'
                            )

                            # Save results
                            output_file = output_path / f"{file_path.stem}_ocr.{format}"
                            if format == 'json':
                                import json
                                async with aiofiles.open(output_file, 'w') as f:
                                    await f.write(json.dumps(result, indent=2))
                            else:
                                async with aiofiles.open(output_file, 'w') as f:
                                    await f.write(result['text'])

                            progress.update(main_task, advance=1)
                            return True

                        except Exception as e:
                            console.print(f"[red]Failed to process {file_path.name}: {str(e)}[/red]")
                            return False

                for file_path in files:
                    tasks.append(asyncio.create_task(process_file(file_path)))

                results = await asyncio.gather(*tasks)
                return results

            # Run batch processing
            results = asyncio.run(process_batch())

            # Display summary
            success_count = sum(1 for r in results if r)
            console.print(f"\n[green]Successfully processed {success_count}/{len(files)} files[/green]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    OCR_COMMAND_GROUP()