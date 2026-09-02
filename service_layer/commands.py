"""Service layer commands (write operations)."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from domain.value_objects import Money, Currency, TicketQuantity, AttendeeInfo, Seat
from domain.models import Order, Payment, Plan
from domain.events import (
    OrderCreated, PaymentInitiated, PaymentConfirmed,
    PaymentFailed, OrderConfirmed, OrderCancelled
)
from domain.repositories import (
    OrderRepository, PaymentRepository, PlanRepository,
    OrderReadRepository, PlanReadRepository,
    PlanSearchQuery
)


@dataclass
class CreateOrderCommand:
    plan_id: UUID
    quantity: int
    attendee_info: AttendeeInfo
    seat_ids: list[str] = None  # Will be validated against plan


@dataclass
class ConfirmPaymentCommand:
    order_id: UUID
    payment_intent_id: str
    idempotency_key: str


@dataclass
class CancelOrderCommand:
    order_id: UUID
    reason: str


@dataclass
class RefundOrderCommand:
    order_id: UUID
    amount: Optional[Money] = None
    reason: str = "Customer request"


@dataclass
class SyncPlansCommand:
    since: Optional[datetime] = None
    stale_only: bool = False


@dataclass
class ReserveSeatsCommand:
    order_id: UUID
    seats: list[Seat]


# Results
@dataclass
class OrderCreatedResult:
    order_id: UUID
    payment_intent_id: str
    client_secret: str
    status: str


@dataclass
class PaymentConfirmedResult:
    order_id: UUID
    payment_id: UUID
    status: str
    provider_ref: str


@dataclass
class PlanSearchResult:
    plans: list
    cursor: Optional[str]
    has_more: bool


@dataclass
class PlanDetail:
    plan_id: UUID
    tm_plan_id: str
    name: str
    url: str
    image_url: Optional[str]
    date_range: object
    venue_name: str
    venue_city: str
    venue_state: str
    min_price: float
    max_price: float
    currency: str
    seat_map: list


@dataclass
class OrderStatusResult:
    order_id: UUID
    plan_id: UUID
    plan_name: str
    status: str
    quantity: int
    total_amount: float
    currency: str
    seats: list
    payment_id: Optional[UUID]
    created_at: str
    updated_at: str