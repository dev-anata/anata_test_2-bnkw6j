"""
Distributed tracing implementation using OpenTelemetry with Google Cloud Trace integration.

This module provides comprehensive tracing functionality with:
- OpenTelemetry integration
- Google Cloud Trace export
- Trace context propagation
- Performance monitoring
- Error tracking
- Sampling configuration

Version: 1.0.0
"""

from typing import Dict, Optional, Any  # version: 3.11+
from contextlib import contextmanager
import json

from opentelemetry import trace  # version: 1.19+
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter  # version: 1.19+
from opentelemetry.sdk.trace import TracerProvider, sampling  # version: 1.19+
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # version: 1.19+
from opentelemetry.propagate import extract, inject, set_global_textmap  # version: 1.19+
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator  # version: 1.19+

from config.settings import settings
from monitoring.logger import Logger

# Global constants
TRACE_HEADER_KEY = 'X-Cloud-Trace-Context'
SAMPLING_RATE = 0.1  # 10% sampling rate for production

# Cache for tracer instances
_TRACERS = {}

def configure_tracing() -> None:
    """
    Initialize and configure the tracing system with Cloud Trace integration.
    
    Configures:
    - Tracer provider with sampling
    - Cloud Trace exporter
    - Batch span processor
    - W3C trace context propagation
    """
    # Create Cloud Trace exporter
    exporter = CloudTraceSpanExporter(
        project_id=settings.project_id,
        client_info={'client_library': 'opentelemetry-python'}
    )
    
    # Configure sampling based on environment
    if settings.env == 'production':
        sampler = sampling.TraceIdRatioBased(SAMPLING_RATE)
    else:
        sampler = sampling.AlwaysOnSampler()
    
    # Initialize tracer provider with sampling
    provider = TracerProvider(sampler=sampler)
    
    # Configure batch processor with retry settings
    processor = BatchSpanProcessor(
        exporter,
        max_export_batch_size=100,
        schedule_delay_millis=5000
    )
    provider.add_span_processor(processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    # Configure W3C trace context propagation
    set_global_textmap(TraceContextTextMapPropagator())

def get_tracer(name: str) -> trace.Tracer:
    """
    Get or create a tracer instance with caching.
    
    Args:
        name: Name for the tracer instance
        
    Returns:
        Configured tracer instance
    """
    if name not in _TRACERS:
        _TRACERS[name] = trace.get_tracer(
            name,
            schema_url="https://opentelemetry.io/schemas/1.19.0"
        )
    return _TRACERS[name]

def extract_trace_context(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Extract and validate trace context from request headers.
    
    Args:
        headers: Request headers dictionary
        
    Returns:
        Dictionary containing validated trace context
    """
    context = {}
    
    # Extract trace context using W3C propagation
    carrier = {
        key.lower(): value
        for key, value in headers.items()
    }
    
    # Handle Cloud Trace header if present
    if TRACE_HEADER_KEY.lower() in carrier:
        try:
            trace_value = carrier[TRACE_HEADER_KEY.lower()]
            trace_id, span_id = trace_value.split('/')
            context.update({
                'trace_id': trace_id,
                'span_id': span_id.split(';')[0] if ';' in span_id else span_id
            })
        except (ValueError, IndexError):
            pass
    
    # Extract W3C trace context
    ctx = extract(carrier)
    if ctx:
        span_context = ctx.get_current_span().get_span_context()
        if span_context.is_valid:
            context.update({
                'traceparent': f'00-{span_context.trace_id}-{span_context.span_id}-{span_context.trace_flags:02x}'
            })
    
    return context

class TraceContextManager:
    """
    Context manager for creating and managing trace spans with enhanced error handling.
    """
    
    def __init__(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize trace context manager.
        
        Args:
            name: Name for the span
            attributes: Optional span attributes
        """
        self._tracer = get_tracer(__name__)
        self._name = name
        self._attributes = attributes or {}
        self._current_span = None
        
        # Initialize logger
        self._logger = Logger(__name__)

    def __enter__(self) -> trace.Span:
        """
        Enter trace context and start span.
        
        Returns:
            Active trace span
        """
        # Start new span
        self._current_span = self._tracer.start_span(
            name=self._name,
            attributes=self._attributes
        )
        
        # Set span as current
        context = trace.set_span_in_context(self._current_span)
        
        # Bind trace context to logger
        self._logger.bind_context({
            'trace_id': self._current_span.get_span_context().trace_id,
            'span_id': self._current_span.get_span_context().span_id
        })
        
        return self._current_span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit trace context with error handling.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        if self._current_span:
            try:
                if exc_val:
                    # Record exception details
                    self._current_span.record_exception(
                        exc_val,
                        attributes={
                            'error.type': exc_type.__name__,
                            'error.message': str(exc_val)
                        }
                    )
                    self._current_span.set_status(trace.Status(trace.StatusCode.ERROR))
                
                # End span
                self._current_span.end()
            finally:
                self._current_span = None