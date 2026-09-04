"""Application configuration using Pydantic Settings v2."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ticket_genius",
        description="PostgreSQL connection URL",
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    echo: bool = Field(default=False, description="Log SQL queries")


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    max_connections: int = Field(default=20, description="Max Redis connections")
    socket_timeout: int = Field(default=5, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, description="Socket connect timeout")


class TicketmasterSettings(BaseSettings):
    """Ticketmaster API configuration."""

    model_config = SettingsConfigDict(env_prefix="TM_")

    client_id: str = Field(default="test", description="Ticketmaster API key (client_id)")
    client_secret: str = Field(default="test", description="Ticketmaster API secret")
    sandbox: bool = Field(default=True, description="Use sandbox environment")
    base_url: str = Field(
        default="https://app.ticketmaster.com/discovery/v2",
        description="Ticketmaster Discovery API base URL",
    )
    oauth_url: str = Field(
        default="https://oauth.ticketmaster.com/oauth/token",
        description="Ticketmaster OAuth token URL",
    )
    rate_limit_capacity: int = Field(default=5, description="Token bucket capacity")
    rate_limit_refill_rate: float = Field(
        default=5.0, description="Token bucket refill rate per second"
    )
    request_timeout: float = Field(default=10.0, description="HTTP request timeout in seconds")
    connect_timeout: float = Field(default=30.0, description="HTTP connect timeout in seconds")
    max_retries: int = Field(default=3, description="Max retry attempts")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds (5 min)")


class PaymentSettings(BaseSettings):
    """Payment adapter configuration."""

    model_config = SettingsConfigDict(env_prefix="PAYMENT_")

    test_mode: bool = Field(default=True, description="Use simulated payment adapter")
    stripe_api_key: str | None = Field(default=None, description="Stripe API key (for production)")
    stripe_webhook_secret: str | None = Field(default=None, description="Stripe webhook secret")
    failure_threshold_cents: int = Field(
        default=10000, description="Amount in cents that triggers simulated failure"
    )


class AppSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # App
    name: str = Field(default="Ticket Genius", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    env: str = Field(
        default="development", description="Environment (development, staging, production)"
    )
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="0.0.0.0", description="Host to bind")
    port: int = Field(default=5000, description="Port to bind")

    # Security
    secret_key: str = Field(
        default="dev-secret-change-in-production", description="Secret key for sessions/JWT"
    )
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ticketmaster: TicketmasterSettings = Field(default_factory=TicketmasterSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)

    # Observability
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    log_format: str = Field(default="json", description="Log format (json, console)")
    otel_endpoint: str | None = Field(default=None, description="OpenTelemetry OTLP endpoint")
    otel_service_name: str = Field(default="ticket-genius", description="OTel service name")
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")


@lru_cache
def get_settings() -> AppSettings:
    """Get cached settings instance."""
    return AppSettings()


# For backwards compatibility and easy access
settings = get_settings()
