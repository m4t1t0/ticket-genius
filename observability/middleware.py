"""Flask middleware for observability (correlation ID, request logging)."""

import uuid
from flask import Flask, Request, g, request
from observability.logging import (
    get_logger,
    set_correlation_id,
    clear_correlation_id,
    get_correlation_id,
)

logger = get_logger(__name__)


def init_observability(app: Flask) -> None:
    """Initialize observability middleware for Flask app."""
    
    @app.before_request
    def before_request() -> None:
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        # Store in Flask g for access in routes
        g.correlation_id = correlation_id
        
        # Add to response headers
        # (will be set in after_request)

        # Log incoming request
        logger.info(
            "request_started",
            method=request.method,
            path=request.path,
            query_params=dict(request.args),
            correlation_id=correlation_id,
        )

    @app.after_request
    def after_request(response):
        # Add correlation ID to response headers
        correlation_id = get_correlation_id()
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id
        
        # Log response
        logger.info(
            "request_completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            correlation_id=correlation_id,
        )
        
        clear_correlation_id()
        return response

    @app.teardown_request
    def teardown_request(exception=None):
        if exception:
            logger.error(
                "request_failed",
                method=request.method,
                path=request.path,
                error=str(exception),
                correlation_id=get_correlation_id(),
                exc_info=exception,
            )
        clear_correlation_id()