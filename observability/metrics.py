"""Prometheus metrics for business and technical observability."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

# Business metrics
orders_created_total = Counter(
    "orders_created_total",
    "Total number of orders created",
    ["status"],
)

payments_succeeded_total = Counter(
    "payments_succeeded_total",
    "Total number of successful payments",
)

payments_failed_total = Counter(
    "payments_failed_total",
    "Total number of failed payments",
    ["reason"],
)

orders_cancelled_total = Counter(
    "orders_cancelled_total",
    "Total number of cancelled orders",
)

orders_refunded_total = Counter(
    "orders_refunded_total",
    "Total number of refunded orders",
)

plans_synced_total = Counter(
    "plans_synced_total",
    "Total number of plans synced from Ticketmaster",
)

seat_holds_conflicts_total = Counter(
    "seat_holds_conflicts_total",
    "Total number of seat hold conflicts",
)

# Latency histograms
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

tm_search_latency_seconds = Histogram(
    "tm_search_latency_seconds",
    "Ticketmaster search API latency in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

tm_purchase_latency_seconds = Histogram(
    "tm_purchase_latency_seconds",
    "Ticketmaster purchase API latency in seconds",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

payment_latency_seconds = Histogram(
    "payment_latency_seconds",
    "Payment processing latency in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Gauges
active_orders_gauge = Gauge(
    "active_orders",
    "Number of orders in non-terminal states",
)

outbox_lag_seconds = Gauge(
    "outbox_lag_seconds",
    "Age of oldest unprocessed outbox event in seconds",
)

redis_connected = Gauge(
    "redis_connected",
    "Redis connection status (1=connected, 0=disconnected)",
)


def record_order_created(status: str) -> None:
    """Record order creation."""
    orders_created_total.labels(status=status).inc()
    active_orders_gauge.inc()


def record_order_completed() -> None:
    """Record order completion (fulfilled/cancelled/refunded)."""
    active_orders_gauge.dec()


def record_payment_succeeded() -> None:
    """Record successful payment."""
    payments_succeeded_total.inc()


def record_payment_failed(reason: str) -> None:
    """Record failed payment."""
    payments_failed_total.labels(reason=reason).inc()


def record_order_cancelled() -> None:
    """Record order cancellation."""
    orders_cancelled_total.inc()
    active_orders_gauge.dec()


def record_order_refunded() -> None:
    """Record order refund."""
    orders_refunded_total.inc()


def record_plans_synced(count: int) -> None:
    """Record plans synced."""
    plans_synced_total.inc(count)


def record_seat_hold_conflict() -> None:
    """Record seat hold conflict."""
    seat_holds_conflicts_total.inc()


def metrics_endpoint() -> Response:
    """Prometheus /metrics endpoint."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)