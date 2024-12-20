"""
Centralized monitoring package providing comprehensive observability features.

This module serves as the main entry point for the monitoring subsystem, integrating:
- Structured logging with Cloud Logging
- Metrics collection with Prometheus
- Distributed tracing with OpenTelemetry
- System health monitoring
- Performance tracking
- Error reporting

Version: 1.0.0
"""

# Import monitoring components
from monitoring.logger import Logger, get_logger, configure_logging
from monitoring.metrics import (
    MetricsManager, track_request_duration, track_task_duration,
    record_task_status, track_storage_operation, record_error
)
from monitoring.tracing import (
    configure_tracing, get_tracer, TraceContextManager,
    extract_trace_context
)

# Export monitoring components
__all__ = [
    # Logging components
    "Logger",
    "get_logger",
    "configure_logging",
    # Metrics components
    "MetricsManager",
    "track_request_duration",
    "track_task_duration",
    "record_task_status", 
    "track_storage_operation",
    "record_error",
    # Tracing components
    "configure_tracing",
    "get_tracer",
    "TraceContextManager",
    "extract_trace_context",
    # Initialization function
    "initialize_monitoring"
]

def initialize_monitoring() -> None:
    """
    Initialize all monitoring subsystems with comprehensive configuration.
    
    This function:
    1. Configures structured logging with Cloud Logging integration
    2. Initializes metrics collection with Prometheus
    3. Sets up distributed tracing with OpenTelemetry
    4. Starts metrics server for scraping
    5. Configures system health monitoring
    
    Raises:
        RuntimeError: If initialization of any monitoring component fails
    """
    try:
        # Get logger for initialization
        logger = get_logger("monitoring.init")
        logger.info("Starting monitoring initialization")

        # Configure logging system
        logger.info("Configuring logging system")
        configure_logging()

        # Initialize tracing
        logger.info("Configuring distributed tracing")
        configure_tracing()

        # Initialize metrics collection
        logger.info("Initializing metrics collection")
        metrics_manager = MetricsManager({
            'alerts': {
                'error_rate_threshold': 0.01,
                'latency_threshold_ms': 500,
                'resource_utilization_threshold': 0.8
            },
            'persistence': {
                'enabled': True,
                'retention_days': 30
            },
            'labels': {
                'environment': 'production',
                'service': 'data_pipeline'
            }
        })

        # Start metrics server
        logger.info("Starting metrics server")
        metrics_manager.start_metrics_server(
            port=8000,
            security_config={
                'local_only': False
            }
        )

        # Initialize system metrics collection
        logger.info("Starting system metrics collection")
        metrics_manager.collect_system_metrics()

        logger.info(
            "Monitoring initialization completed successfully",
            extra={
                "components": [
                    "logging",
                    "metrics",
                    "tracing",
                    "system_monitoring"
                ]
            }
        )

    except Exception as e:
        # Get a new logger instance in case the error occurred during logger setup
        error_logger = get_logger("monitoring.init.error")
        error_logger.error(
            "Failed to initialize monitoring system",
            exc=e,
            extra={
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )
        raise RuntimeError("Monitoring initialization failed") from e