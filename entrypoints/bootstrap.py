"""Bootstrap - dependency injection wiring."""

import signal
import sys
import threading

from config import get_settings
from container import create_container
from observability import configure_logging, init_tracing, metrics_endpoint
from observability.middleware import init_observability
from service_layer import MessageBus

# Global shutdown event for graceful shutdown
shutdown_event = threading.Event()


def load_manual_openapi_spec():
    """Load manual OpenAPI spec from YAML file for Swagger UI and /openapi.json."""
    import os

    import yaml

    spec_path = os.path.join(os.path.dirname(__file__), "..", "docs", "openapi.yaml")
    with open(spec_path) as f:
        return yaml.safe_load(f)


def bootstrap(config: dict | None = None) -> MessageBus:
    """
    Bootstrap the application with all dependencies wired via DI container.

    Args:
        config: Optional configuration dict (for testing overrides)

    Returns:
        Configured MessageBus instance
    """
    container = create_container()

    # Override config if provided (mainly for testing)
    if config:
        if "database_url" in config:
            container.config.database.url.from_value(config["database_url"])
        if "tm_client_id" in config:
            container.config.ticketmaster.client_id.from_value(config["tm_client_id"])
        if "tm_client_secret" in config:
            container.config.ticketmaster.client_secret.from_value(config["tm_client_secret"])
        if "test_mode" in config:
            container.config.payment.test_mode.from_value(config["test_mode"])
        if "sandbox" in config:
            container.config.ticketmaster.sandbox.from_value(config["sandbox"])

    return container.message_bus()


def create_app(config: dict | None = None):
    """Flask app factory with bootstrapped message bus via DI container."""
    from dotenv import load_dotenv
    from flask import Flask, jsonify, render_template_string

    load_dotenv()

    # Initialize structured logging
    settings = get_settings()
    configure_logging(level=settings.log_level, format=settings.log_format)

    # Initialize OpenTelemetry tracing
    if settings.otel_endpoint:
        init_tracing(service_name=settings.otel_service_name, otlp_endpoint=settings.otel_endpoint)

    message_bus = bootstrap(config)

    app = Flask(__name__)
    app.message_bus = message_bus

    # Initialize observability middleware (correlation ID, request logging)
    init_observability(app)

    # Prometheus metrics endpoint
    if settings.metrics_enabled:
        app.add_url_rule("/metrics", "metrics", metrics_endpoint)

    # Load manual OpenAPI spec for Swagger UI and /openapi.json
    manual_spec = load_manual_openapi_spec()

    @app.route("/")
    def index():
        return {
            "name": "Ticket Genius",
            "description": "Ticketing platform aggregating events from Ticketmaster and enabling ticket purchases",
            "version": "0.1.0",
            "status": "development",
        }

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/health/ready")
    def health_ready():
        """Readiness check - verifies DB, Redis, and TM connectivity."""
        from observability import get_logger

        logger = get_logger(__name__)

        checks = {}
        all_healthy = True

        # Use public methods on MessageBus
        db_ok = message_bus.check_database()
        checks["database"] = "ok" if db_ok else "failed"
        if not db_ok:
            all_healthy = False
            logger.warning("readiness_check_database_failed")

        redis_ok = message_bus.check_redis()
        checks["redis"] = (
            "ok" if redis_ok else ("not_configured" if redis_ok is False else "failed")
        )
        if not redis_ok:
            all_healthy = False
            logger.warning("readiness_check_redis_failed")

        tm_ok = message_bus.check_ticketmaster()
        checks["ticketmaster"] = "ok" if tm_ok else "no_token"
        if not tm_ok:
            all_healthy = False
            logger.warning("readiness_check_ticketmaster_failed")

        status_code = 200 if all_healthy else 503
        return jsonify(
            {"status": "ready" if all_healthy else "not_ready", "checks": checks}
        ), status_code

    # Swagger UI endpoint - serve manual OpenAPI spec with Swagger UI
    @app.route("/docs")
    def swagger_ui():
        return render_template_string(
            """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ticket Genius API - Swagger UI</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
  <style>
    html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin: 0; background: #fafafa; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      const ui = SwaggerUIBundle({
        spec: {{ spec_json | tojson }},
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout"
      });
      window.ui = ui;
    };
  </script>
</body>
</html>
        """,
            spec_json=manual_spec,
        )

    # OpenAPI spec endpoint (manual YAML spec)
    @app.route("/openapi.json")
    def openapi_json():
        return jsonify(manual_spec)

    # Register API routes
    from entrypoints.api import register_routes

    bp = register_routes(message_bus)
    app.register_blueprint(bp)

    # Graceful shutdown handling
    def shutdown_handler(signum, frame):
        from observability import get_logger

        logger = get_logger(__name__)
        logger.info("shutdown_signal_received", signal=signum)
        shutdown_event.set()

        # Use public shutdown method on MessageBus
        try:
            message_bus.shutdown()
            logger.info("shutdown_complete")
        except Exception as e:
            logger.error("shutdown_failed", error=str(e))

        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    return app
