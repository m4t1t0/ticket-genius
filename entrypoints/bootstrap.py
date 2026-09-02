"""Bootstrap - dependency injection wiring."""
import os
from typing import Optional

from redis import Redis
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_apispec import FlaskApiSpec

from adapters import (
    SqlAlchemyUnitOfWork,
    TicketmasterAdapter,
    PaymentSimulatorAdapter,
)
from service_layer import (
    OrderCommandHandler,
    PlanCommandHandler,
    QueryHandler,
    MessageBus,
)


def get_redis_client() -> Optional[Redis]:
    """Get Redis client from environment."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return Redis.from_url(redis_url, decode_responses=True)
    return None


def create_api_spec(app):
    """Create and configure APISpec for OpenAPI documentation (used for /openapi.json only)."""
    spec = APISpec(
        title="Ticket Genius API",
        version="0.1.0",
        openapi_version="3.0.3",
        plugins=[MarshmallowPlugin()],
    )
    
    # Add security schemes
    spec.components.security_scheme("BearerAuth", {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    })
    
    docs = FlaskApiSpec(app)
    app.config['APISPEC_SPEC'] = spec
    return docs


def load_manual_openapi_spec():
    """Load manual OpenAPI spec from YAML file for Swagger UI."""
    import yaml
    spec_path = os.path.join(os.path.dirname(__file__), "..", "docs", "openapi.yaml")
    with open(spec_path, 'r') as f:
        return yaml.safe_load(f)


def bootstrap(config: Optional[dict] = None) -> MessageBus:
    """
    Bootstrap the application with all dependencies wired.
    
    Args:
        config: Optional configuration dict with:
            - database_url: PostgreSQL/SQLite connection string
            - tm_client_id: Ticketmaster API key
            - tm_client_secret: Ticketmaster API secret
            - test_mode: Use simulated payment adapter
    
    Returns:
        Configured MessageBus instance
    """
    config = config or {}

    # Database
    database_url = config.get("database_url") or os.getenv("DATABASE_URL", "sqlite:///ticket_genius.db")
    uow = SqlAlchemyUnitOfWork(database_url)

    # Redis
    redis = get_redis_client()

    # Ticketmaster adapter
    tm_client_id = config.get("tm_client_id") or os.getenv("TM_API_KEY", "test")
    tm_client_secret = config.get("tm_client_secret") or os.getenv("TM_API_SECRET", "test")
    tm_adapter = TicketmasterAdapter(
        client_id=tm_client_id,
        client_secret=tm_client_secret,
        redis_client=redis,
        sandbox=config.get("sandbox", True),
    )

    # Payment adapter
    test_mode = config.get("test_mode", True)
    if test_mode:
        payment_adapter = PaymentSimulatorAdapter()
    else:
        # Would use StripeAdapter here
        payment_adapter = PaymentSimulatorAdapter()  # fallback

    # Handlers
    order_handler = OrderCommandHandler(uow, tm_adapter, payment_adapter)
    plan_handler = PlanCommandHandler(uow, tm_adapter)
    query_handler = QueryHandler(uow)

    # Message bus
    message_bus = MessageBus(order_handler, plan_handler, query_handler)

    return message_bus


def create_app(config: Optional[dict] = None):
    """Flask app factory with bootstrapped message bus."""
    from flask import Flask, render_template_string
    from dotenv import load_dotenv

    load_dotenv()

    message_bus = bootstrap(config)

    app = Flask(__name__)
    app.message_bus = message_bus

    # OpenAPI documentation (for /openapi.json only)
    docs = create_api_spec(app)

    # Load manual OpenAPI spec for Swagger UI
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

    # Swagger UI endpoint - serve manual OpenAPI spec with Swagger UI
    @app.route("/docs")
    def swagger_ui():
        return render_template_string('''
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
        ''', spec_json=manual_spec)

    # Register API routes
    from entrypoints.api import register_routes
    bp = register_routes(message_bus)
    app.register_blueprint(bp)

    # Register OpenAPI spec endpoint (from flask-apispec)
    @app.route("/openapi.json")
    def openapi_json():
        return docs.spec.to_dict()

    return app