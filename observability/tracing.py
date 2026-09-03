"""OpenTelemetry tracing setup."""

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes


def init_tracing(
    service_name: str = "ticket-genius",
    otlp_endpoint: Optional[str] = None,
) -> None:
    """
    Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service for tracing
        otlp_endpoint: OTLP endpoint (e.g., http://localhost:4318/v1/traces)
    """
    # Create resource with service info
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("APP_ENV", "development"),
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter if endpoint provided
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Auto-instrument libraries
    FlaskInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)


def add_span_attributes(**kwargs) -> None:
    """Add attributes to current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in kwargs.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """Record exception on current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))