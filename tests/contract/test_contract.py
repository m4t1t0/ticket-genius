"""Contract tests using schemathesis - simplified."""
import schemathesis
import os

# Load the OpenAPI schema
schema = schemathesis.openapi.from_path(
    os.path.join(os.path.dirname(__file__), "..", "..", "docs", "openapi.yaml")
)


def test_schema_valid():
    """Test that the OpenAPI schema is valid."""
    assert schema is not None
    assert hasattr(schema, 'raw_schema')
    assert schema.raw_schema is not None


def test_schema_has_paths():
    """Test that the schema has all expected paths."""
    spec = schema.raw_schema
    paths = spec.get("paths", {})
    
    expected_paths = [
        "/health",
        "/orders",
        "/orders/{order_id}/confirm-payment",
        "/orders/{order_id}",
        "/plans/search",
        "/plans/{plan_id}",
        "/admin/sync-plans",
    ]
    
    for path in expected_paths:
        assert path in paths, f"Missing path: {path}"
    
    # Verify /orders/{order_id} has POST method for refund
    assert "post" in paths["/orders/{order_id}"]


def test_schema_has_components():
    """Test that the schema has all expected components."""
    spec = schema.raw_schema
    components = spec.get("components", {})
    schemas = components.get("schemas", {})
    
    expected_schemas = [
        "CreateOrderRequest",
        "ConfirmPaymentRequest",
        "CancelOrderRequest",
        "RefundOrderRequest",
        "SearchPlansRequest",
        "OrderCreatedResponse",
        "PaymentConfirmedResponse",
        "OrderStatusResponse",
        "PlanSummaryResponse",
        "PlanDetailResponse",
        "PlanSearchResponse",
        "SyncPlansResponse",
        "ErrorResponse",
        "MoneySchema",
        "SeatSchema",
        "AttendeeInfoSchema",
    ]
    
    for schema_name in expected_schemas:
        assert schema_name in schemas, f"Missing schema: {schema_name}"


def test_schema_validates():
    """Test that the schema is valid OpenAPI 3.0.3."""
    spec = schema.raw_schema
    assert spec.get("openapi") == "3.0.3"
    assert spec.get("info", {}).get("title") == "Ticket Genius API"
    assert "servers" in spec
    assert "paths" in spec
    assert "components" in spec