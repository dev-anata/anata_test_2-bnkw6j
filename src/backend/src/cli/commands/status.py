"""
CLI implementation for status commands providing comprehensive system and task monitoring.

This module implements the status command group for the CLI, enabling users to:
- Monitor task execution status with detailed metrics
- View system health and performance indicators
- Track resource utilization and alerts

Version: 1.0.0
"""

import click  # version: 8.1+
from tabulate import tabulate  # version: 0.9+
import structlog  # version: 23.1+
from prometheus_client import CollectorRegistry, Counter, Gauge  # version: 0.17+
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from services.task_service import TaskService
from core.types import TaskType, TaskStatus, TaskID
from core.exceptions import CLIException, MetricsException

# Configure structured logger
logger = structlog.get_logger(__name__)

# Metrics configuration
METRICS_COLLECTION_INTERVAL = 60  # seconds

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "api_latency_ms": 500,
    "cpu_usage_percent": 80,
    "memory_usage_percent": 80,
    "error_rate": 0.01
}

# Initialize metrics registry
registry = CollectorRegistry()

# Define metrics
task_status_counter = Counter(
    'pipeline_task_status_total',
    'Total number of tasks by status',
    ['status'],
    registry=registry
)

system_metrics = {
    'cpu_usage': Gauge(
        'pipeline_cpu_usage_percent',
        'Current CPU usage percentage',
        registry=registry
    ),
    'memory_usage': Gauge(
        'pipeline_memory_usage_percent',
        'Current memory usage percentage',
        registry=registry
    ),
    'api_latency': Gauge(
        'pipeline_api_latency_ms',
        'API request latency in milliseconds',
        registry=registry
    )
}

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string."""
    duration = timedelta(seconds=seconds)
    days = duration.days
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)

@click.group(name='status')
@click.pass_context
def status_group(ctx: click.Context) -> None:
    """
    Monitor system and task status with detailed metrics.
    
    Provides commands for viewing:
    - Task execution status and metrics
    - System health and performance
    - Resource utilization and alerts
    """
    # Initialize services
    ctx.ensure_object(dict)
    ctx.obj['task_service'] = TaskService()
    
    logger.debug("Initialized status command group")

@status_group.command(name='tasks')
@click.option(
    '--status',
    type=click.Choice(['pending', 'running', 'completed', 'failed', 'cancelled']),
    help='Filter tasks by status'
)
@click.option(
    '--format',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='Output format'
)
@click.option(
    '--show-metrics/--no-metrics',
    default=False,
    help='Include task performance metrics'
)
@click.option(
    '--limit',
    type=int,
    default=50,
    help='Maximum number of tasks to display'
)
@click.pass_context
async def tasks_command(
    ctx: click.Context,
    status: Optional[TaskStatus],
    format: str,
    show_metrics: bool,
    limit: int
) -> None:
    """
    Display task status with optional filtering and metrics.
    
    Shows task execution status, progress, and performance metrics
    with support for filtering and different output formats.
    """
    try:
        task_service = ctx.obj['task_service']
        
        # Get tasks with optional status filter
        tasks = await task_service.list_tasks(status=status, limit=limit)
        
        # Collect task metrics if requested
        metrics = {}
        if show_metrics:
            for task in tasks:
                task_metrics = await task_service.get_task_metrics(task.id)
                metrics[task.id] = task_metrics
        
        # Format output
        if format == 'table':
            headers = ['ID', 'Type', 'Status', 'Created', 'Duration']
            if show_metrics:
                headers.extend(['CPU %', 'Memory %', 'Error Rate'])
            
            rows = []
            for task in tasks:
                row = [
                    str(task.id),
                    task.type,
                    task.status,
                    task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    format_duration((datetime.utcnow() - task.created_at).total_seconds())
                ]
                
                if show_metrics and task.id in metrics:
                    m = metrics[task.id]
                    row.extend([
                        f"{m['cpu_percent']:.1f}",
                        f"{m['memory_percent']:.1f}",
                        f"{m['error_rate']:.2%}"
                    ])
                
                rows.append(row)
            
            click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
            
        elif format == 'json':
            import json
            output = {
                'tasks': [
                    {
                        'id': str(t.id),
                        'type': t.type,
                        'status': t.status,
                        'created_at': t.created_at.isoformat(),
                        'metrics': metrics.get(t.id) if show_metrics else None
                    }
                    for t in tasks
                ]
            }
            click.echo(json.dumps(output, indent=2))
            
        elif format == 'yaml':
            import yaml
            output = {
                'tasks': [
                    {
                        'id': str(t.id),
                        'type': t.type,
                        'status': t.status,
                        'created_at': t.created_at.isoformat(),
                        'metrics': metrics.get(t.id) if show_metrics else None
                    }
                    for t in tasks
                ]
            }
            click.echo(yaml.dump(output, sort_keys=False))
        
        # Update metrics
        for task in tasks:
            task_status_counter.labels(status=task.status).inc()
        
        logger.info(
            "Retrieved task status",
            task_count=len(tasks),
            status_filter=status,
            show_metrics=show_metrics
        )

    except Exception as e:
        logger.error("Failed to retrieve task status", error=str(e))
        raise CLIException("Failed to retrieve task status") from e

@status_group.command(name='system')
@click.option(
    '--format',
    type=click.Choice(['table', 'json', 'yaml']),
    default='table',
    help='Output format'
)
@click.option(
    '--component',
    type=click.Choice(['api', 'worker', 'storage', 'all']),
    default='all',
    help='System component to monitor'
)
@click.option(
    '--show-alerts/--no-alerts',
    default=True,
    help='Show active alerts'
)
@click.pass_context
async def system_command(
    ctx: click.Context,
    format: str,
    component: str,
    show_alerts: bool
) -> None:
    """
    Display system health metrics and performance indicators.
    
    Shows detailed system metrics including:
    - Resource utilization (CPU, memory, storage)
    - API performance metrics
    - Active alerts and warnings
    """
    try:
        # Collect system metrics
        metrics = {
            'api': {
                'latency_ms': system_metrics['api_latency'].get(),
                'error_rate': task_status_counter.labels(status='failed').get() / 
                             sum(task_status_counter.labels(status=s).get() 
                                 for s in ['completed', 'failed'])
            },
            'resources': {
                'cpu_percent': system_metrics['cpu_usage'].get(),
                'memory_percent': system_metrics['memory_usage'].get()
            },
            'tasks': {
                status: task_status_counter.labels(status=status).get()
                for status in ['pending', 'running', 'completed', 'failed']
            }
        }
        
        # Check for alerts
        alerts = []
        if show_alerts:
            if metrics['api']['latency_ms'] > PERFORMANCE_THRESHOLDS['api_latency_ms']:
                alerts.append({
                    'severity': 'WARNING',
                    'component': 'api',
                    'message': f"High API latency: {metrics['api']['latency_ms']:.1f}ms"
                })
            
            if metrics['resources']['cpu_percent'] > PERFORMANCE_THRESHOLDS['cpu_usage_percent']:
                alerts.append({
                    'severity': 'WARNING',
                    'component': 'system',
                    'message': f"High CPU usage: {metrics['resources']['cpu_percent']:.1f}%"
                })
            
            if metrics['resources']['memory_percent'] > PERFORMANCE_THRESHOLDS['memory_usage_percent']:
                alerts.append({
                    'severity': 'WARNING',
                    'component': 'system',
                    'message': f"High memory usage: {metrics['resources']['memory_percent']:.1f}%"
                })
        
        # Format output
        if format == 'table':
            # System metrics table
            if component in ['all', 'api']:
                click.echo("\nAPI Metrics:")
                headers = ['Metric', 'Value', 'Threshold', 'Status']
                rows = [
                    ['Latency (ms)', f"{metrics['api']['latency_ms']:.1f}",
                     PERFORMANCE_THRESHOLDS['api_latency_ms'],
                     '🔴' if metrics['api']['latency_ms'] > PERFORMANCE_THRESHOLDS['api_latency_ms'] else '🟢'],
                    ['Error Rate', f"{metrics['api']['error_rate']:.2%}",
                     f"{PERFORMANCE_THRESHOLDS['error_rate']:.2%}",
                     '🔴' if metrics['api']['error_rate'] > PERFORMANCE_THRESHOLDS['error_rate'] else '🟢']
                ]
                click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
            
            if component in ['all', 'worker']:
                click.echo("\nResource Utilization:")
                headers = ['Resource', 'Usage', 'Threshold', 'Status']
                rows = [
                    ['CPU', f"{metrics['resources']['cpu_percent']:.1f}%",
                     f"{PERFORMANCE_THRESHOLDS['cpu_usage_percent']}%",
                     '🔴' if metrics['resources']['cpu_percent'] > PERFORMANCE_THRESHOLDS['cpu_usage_percent'] else '🟢'],
                    ['Memory', f"{metrics['resources']['memory_percent']:.1f}%",
                     f"{PERFORMANCE_THRESHOLDS['memory_usage_percent']}%",
                     '🔴' if metrics['resources']['memory_percent'] > PERFORMANCE_THRESHOLDS['memory_usage_percent'] else '🟢']
                ]
                click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
            
            if show_alerts and alerts:
                click.echo("\nActive Alerts:")
                headers = ['Severity', 'Component', 'Message']
                rows = [[a['severity'], a['component'], a['message']] for a in alerts]
                click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
        
        elif format == 'json':
            import json
            output = {
                'metrics': metrics,
                'alerts': alerts if show_alerts else None,
                'thresholds': PERFORMANCE_THRESHOLDS
            }
            click.echo(json.dumps(output, indent=2))
        
        elif format == 'yaml':
            import yaml
            output = {
                'metrics': metrics,
                'alerts': alerts if show_alerts else None,
                'thresholds': PERFORMANCE_THRESHOLDS
            }
            click.echo(yaml.dump(output, sort_keys=False))
        
        logger.info(
            "Retrieved system status",
            component=component,
            alert_count=len(alerts) if show_alerts else 0
        )

    except Exception as e:
        logger.error("Failed to retrieve system status", error=str(e))
        raise CLIException("Failed to retrieve system status") from e

__all__ = ['status_group']