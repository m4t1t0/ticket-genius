"""Service layer queries (read operations)."""
from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from domain.repositories import PlanSearchQuery, PlanSummary, PlanDetail, OrderSummary, OrderStatusDetail


@dataclass
class SearchPlansQuery:
    query: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    cursor: Optional[str] = None
    limit: int = 20


@dataclass
class GetOrderQuery:
    order_id: UUID


@dataclass
class ListOrdersQuery:
    customer_email: str
    cursor: Optional[str] = None
    limit: int = 20


@dataclass
class GetPlanQuery:
    plan_id: UUID


@dataclass
class PlanSearchResult:
    plans: List[PlanSummary]
    cursor: Optional[str]
    has_more: bool


@dataclass
class OrderSummaryResult:
    order: Optional[OrderSummary]


@dataclass
class OrderStatusResult:
    order: Optional[OrderStatusDetail]