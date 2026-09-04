"""Service layer queries (read operations)."""

from dataclasses import dataclass
from uuid import UUID

from domain.repositories import OrderStatusDetail, OrderSummary, PlanSummary


@dataclass
class SearchPlansQuery:
    query: str | None = None
    lat: float | None = None
    lon: float | None = None
    radius_km: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    cursor: str | None = None
    limit: int = 20


@dataclass
class GetOrderQuery:
    order_id: UUID


@dataclass
class ListOrdersQuery:
    customer_email: str
    cursor: str | None = None
    limit: int = 20


@dataclass
class GetPlanQuery:
    plan_id: UUID


@dataclass
class PlanSearchResult:
    plans: list[PlanSummary]
    cursor: str | None
    has_more: bool


@dataclass
class OrderSummaryResult:
    order: OrderSummary | None


@dataclass
class OrderStatusResult:
    order: OrderStatusDetail | None
