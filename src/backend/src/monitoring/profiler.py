"""
Enterprise-grade performance profiling and resource monitoring system.

This module provides comprehensive profiling capabilities including:
- Function execution profiling with cProfile
- High-precision timing measurements
- System resource monitoring
- Predictive analysis
- Trace context integration
- Metric collection

Version: 1.0.0
"""

import cProfile  # version: 3.11+
import pstats  # version: 3.11+
import time  # version: 3.11+
from functools import wraps  # version: 3.11+
import psutil  # version: 5.9+
from typing import Dict, Any, Optional, Callable, List
from concurrent.futures import ThreadPoolExecutor
import os
import gzip
import json

from monitoring.logger import Logger
from monitoring.metrics import MetricsManager
from monitoring.tracing import TraceContextManager

# Global constants
PROFILE_OUTPUT_DIR = './profiles'
MEMORY_THRESHOLD_PERCENT = 90.0
CPU_THRESHOLD_PERCENT = 80.0

# Initialize core components
logger = Logger(__name__)
metrics_manager = MetricsManager({
    'alerts': {
        'memory_threshold': MEMORY_THRESHOLD_PERCENT,
        'cpu_threshold': CPU_THRESHOLD_PERCENT
    }
})

def profile_function(output_file: str, profile_options: Optional[Dict] = None):
    """
    Enhanced decorator for profiling function execution with comprehensive metrics.

    Args:
        output_file: Path to save profiling data
        profile_options: Optional profiling configuration

    Returns:
        Decorated function with profiling capabilities
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Ensure output directory exists
            os.makedirs(PROFILE_OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(PROFILE_OUTPUT_DIR, output_file)

            # Initialize profiler with options
            profiler = cProfile.Profile()
            if profile_options:
                for key, value in profile_options.items():
                    setattr(profiler, key, value)

            # Create trace context
            with TraceContextManager(f"profile_{func.__name__}") as span:
                try:
                    # Start profiling
                    profiler.enable()
                    start_time = time.perf_counter()
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Stop profiling
                    end_time = time.perf_counter()
                    profiler.disable()

                    # Process profile stats
                    stats = pstats.Stats(profiler)
                    stats.sort_stats('cumulative')

                    # Generate detailed metrics
                    duration = end_time - start_time
                    function_stats = {
                        'duration': duration,
                        'calls': stats.total_calls,
                        'primitive_calls': stats.prim_calls,
                        'total_time': stats.total_tt
                    }

                    # Record metrics
                    metrics_manager.record_profile_metrics(
                        func.__name__,
                        function_stats
                    )

                    # Add profiling events to trace
                    span.add_event(
                        "profile_complete",
                        attributes=function_stats
                    )

                    # Save profile data with compression
                    with gzip.open(f"{output_path}.gz", 'wt') as f:
                        stats.dump_stats(f)

                    logger.info(
                        f"Profile completed for {func.__name__}",
                        extra=function_stats
                    )

                    return result

                except Exception as e:
                    logger.error(
                        f"Profiling failed for {func.__name__}",
                        exc=e
                    )
                    raise

        return wrapper
    return decorator

def time_function(operation_name: Optional[str] = None):
    """
    Enhanced decorator for precise function timing with trace context.

    Args:
        operation_name: Optional name for the timing operation

    Returns:
        Decorated function with timing capabilities
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            with TraceContextManager(f"timer_{op_name}") as span:
                try:
                    # Start timing with high precision
                    start_time = time.perf_counter_ns()

                    # Execute function
                    result = func(*args, **kwargs)

                    # Calculate precise duration
                    end_time = time.perf_counter_ns()
                    duration_ns = end_time - start_time
                    duration_ms = duration_ns / 1_000_000  # Convert to milliseconds

                    # Record detailed timing metrics
                    timing_data = {
                        'operation': op_name,
                        'duration_ms': duration_ms,
                        'timestamp': time.time()
                    }

                    # Add timing event to trace
                    span.add_event(
                        "timing_complete",
                        attributes=timing_data
                    )

                    logger.info(
                        f"Timing completed for {op_name}",
                        extra=timing_data
                    )

                    return result

                except Exception as e:
                    logger.error(
                        f"Timing failed for {op_name}",
                        exc=e
                    )
                    raise

        return wrapper
    return decorator

class ResourceProfiler:
    """
    Advanced system resource profiling and monitoring with predictive analysis.
    """

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        monitoring_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize enhanced resource profiler.

        Args:
            thresholds: Custom threshold values
            monitoring_config: Additional monitoring configuration
        """
        self._logger = Logger(__name__)
        self._metrics_manager = MetricsManager({
            'alerts': thresholds or {
                'memory_threshold': MEMORY_THRESHOLD_PERCENT,
                'cpu_threshold': CPU_THRESHOLD_PERCENT
            }
        })
        
        self._thresholds = thresholds or {}
        self._historical_data: Dict[str, List[Dict[str, Any]]] = {
            'cpu': [],
            'memory': [],
            'disk': []
        }
        self._monitor_pool = ThreadPoolExecutor(max_workers=2)

    def start_monitoring(
        self,
        interval_seconds: int,
        monitoring_options: Optional[Dict] = None
    ) -> None:
        """
        Start comprehensive resource monitoring.

        Args:
            interval_seconds: Monitoring interval
            monitoring_options: Additional monitoring options
        """
        try:
            def monitor_resources():
                while True:
                    try:
                        # Collect CPU metrics
                        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
                        
                        # Collect memory metrics
                        memory = psutil.virtual_memory()
                        
                        # Collect disk metrics
                        disk = psutil.disk_usage('/')

                        # Store historical data
                        timestamp = time.time()
                        self._historical_data['cpu'].append({
                            'timestamp': timestamp,
                            'value': cpu_percent
                        })
                        self._historical_data['memory'].append({
                            'timestamp': timestamp,
                            'value': memory.percent
                        })
                        self._historical_data['disk'].append({
                            'timestamp': timestamp,
                            'value': disk.percent
                        })

                        # Trim historical data (keep last 24 hours)
                        cutoff = timestamp - 86400
                        for resource in self._historical_data:
                            self._historical_data[resource] = [
                                entry for entry in self._historical_data[resource]
                                if entry['timestamp'] > cutoff
                            ]

                        # Record metrics
                        self._metrics_manager.collect_system_metrics()

                        # Check thresholds
                        self._check_thresholds({
                            'cpu': max(cpu_percent),
                            'memory': memory.percent,
                            'disk': disk.percent
                        })

                        time.sleep(interval_seconds)

                    except Exception as e:
                        self._logger.error(
                            "Resource monitoring error",
                            exc=e
                        )
                        time.sleep(interval_seconds)

            # Start monitoring in background
            self._monitor_pool.submit(monitor_resources)
            
            self._logger.info(
                "Resource monitoring started",
                extra={'interval': interval_seconds}
            )

        except Exception as e:
            self._logger.error(
                "Failed to start resource monitoring",
                exc=e
            )
            raise

    def analyze_trends(
        self,
        resource_type: str,
        time_window: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyze resource usage trends with predictive insights.

        Args:
            resource_type: Type of resource to analyze
            time_window: Analysis window in seconds

        Returns:
            Dictionary containing trend analysis and predictions
        """
        try:
            if resource_type not in self._historical_data:
                raise ValueError(f"Invalid resource type: {resource_type}")

            data = self._historical_data[resource_type]
            if not data:
                return {
                    'status': 'no_data',
                    'message': f'No historical data for {resource_type}'
                }

            # Calculate basic statistics
            values = [entry['value'] for entry in data]
            avg_value = sum(values) / len(values)
            max_value = max(values)
            min_value = min(values)

            # Detect trend
            if len(values) > 1:
                trend = 'increasing' if values[-1] > values[0] else 'decreasing'
            else:
                trend = 'stable'

            # Generate analysis
            analysis = {
                'resource_type': resource_type,
                'current_value': values[-1],
                'average_value': avg_value,
                'max_value': max_value,
                'min_value': min_value,
                'trend': trend,
                'samples': len(values),
                'timestamp': time.time()
            }

            self._logger.info(
                f"Trend analysis completed for {resource_type}",
                extra=analysis
            )

            return analysis

        except Exception as e:
            self._logger.error(
                f"Trend analysis failed for {resource_type}",
                exc=e
            )
            raise

    def _check_thresholds(self, metrics: Dict[str, float]) -> None:
        """
        Check resource metrics against thresholds.

        Args:
            metrics: Current resource metrics
        """
        for resource, value in metrics.items():
            threshold = self._thresholds.get(
                f'{resource}_threshold',
                MEMORY_THRESHOLD_PERCENT if resource == 'memory'
                else CPU_THRESHOLD_PERCENT
            )
            
            if value > threshold:
                self._logger.warning(
                    f"{resource} usage exceeds threshold",
                    extra={
                        'resource': resource,
                        'value': value,
                        'threshold': threshold
                    }
                )