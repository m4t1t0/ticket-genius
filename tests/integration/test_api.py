"""Integration tests with testcontainers (skipped if Docker not available)."""

import os

import pytest

# Try to import testcontainers, skip if Docker not available
try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    DOCKER_AVAILABLE = True
except (ImportError, Exception):
    DOCKER_AVAILABLE = False

from adapters.ticketmaster import TicketmasterAdapter
from entrypoints import create_app

pytestmark = pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for integration tests."""
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def redis_container():
    """Start Redis container for integration tests."""
    container = RedisContainer("redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def database_url(postgres_container):
    """Get database URL from container."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def redis_url(redis_container):
    """Get Redis URL from container."""
    return redis_container.get_connection_url()


@pytest.fixture
def app(database_url, redis_url):
    """Create test app with containerized dependencies."""
    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["TM_API_KEY"] = "test"
    os.environ["TM_API_SECRET"] = "test"
    os.environ["APP_ENV"] = "test"

    # Re-import to pick up new env vars
    import importlib

    import entrypoints.bootstrap

    importlib.reload(entrypoints.bootstrap)
    import entrypoints.api

    importlib.reload(entrypoints.api)

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


class TestIntegration:
    """Integration tests for API endpoints."""

    def test_health_endpoints(self, client):
        """Test health check endpoints."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_plans_search_empty(self, client):
        """Test plans search returns empty list initially."""
        resp = client.get("/api/v1/plans/search")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "plans" in data
        assert data["plans"] == []

    def test_get_nonexistent_plan(self, client):
        """Test getting non-existent plan returns 404."""
        resp = client.get("/api/v1/plans/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_create_order_invalid_plan(self, client):
        """Test creating order with invalid plan returns 404."""
        resp = client.post(
            "/api/v1/orders",
            json={
                "plan_id": "00000000-0000-0000-0000-000000000000",
                "quantity": 2,
                "attendee_info": {"name": "John Doe", "email": "john@example.com"},
            },
        )
        assert resp.status_code == 404

    def test_create_order_validation_error(self, client):
        """Test creating order with invalid data returns 400."""
        resp = client.post(
            "/api/v1/orders",
            json={
                "plan_id": "00000000-0000-0000-0000-000000000000",
                "quantity": 10,  # Invalid - max 8
                "attendee_info": {"name": "John Doe", "email": "john@example.com"},
            },
        )
        assert resp.status_code == 400

    def test_get_nonexistent_order(self, client):
        """Test getting non-existent order returns 404."""
        resp = client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_cancel_nonexistent_order(self, client):
        """Test cancelling non-existent order returns 404."""
        resp = client.delete(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000", json={"reason": "Test"}
        )
        assert resp.status_code == 404


class TestDatabaseOperations:
    """Test database operations with real PostgreSQL."""

    def test_database_tables_exist(self, database_url):
        """Verify all tables are created."""
        from sqlalchemy import create_engine, inspect

        engine = create_engine(database_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected_tables = {
            "plans",
            "orders",
            "payments",
            "attendees",
            "seats",
            "outbox",
            "alembic_version",
        }
        for table in expected_tables:
            assert table in tables, f"Table {table} not found"


class TestRedisOperations:
    """Test Redis operations with real Redis."""

    def test_redis_connection(self, redis_url):
        """Test Redis connection works."""
        import redis

        client = redis.from_url(redis_url, decode_responses=True)
        assert client.ping() is True
        client.set("test_key", "test_value")
        assert client.get("test_key") == "test_value"
        client.delete("test_key")


class TestTicketmasterAdapter:
    """Test Ticketmaster adapter (with mocked responses)."""

    def test_adapter_initialization(self, redis_url):
        """Test adapter can be initialized."""
        import redis

        redis_client = redis.from_url(redis_url, decode_responses=True)
        adapter = TicketmasterAdapter(
            client_id="test", client_secret="test", redis_client=redis_client, sandbox=True
        )
        assert adapter is not None
        assert adapter.sandbox is True
