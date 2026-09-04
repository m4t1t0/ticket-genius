"""Service layer commands (write operations)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.value_objects import AttendeeInfo, Money, Seat, SeatId


@dataclass
class CreateOrderCommand:
    plan_id: UUID
    quantity: int
    attendee_info: AttendeeInfo
    seat_ids: list[SeatId] = None  # Will be validated against plan


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
    amount: Money | None = None
    reason: str = "Customer request"


@dataclass
class SyncPlansCommand:
    since: datetime | None = None
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
    cursor: str | None
    has_more: bool


@dataclass
class PlanDetail:
    plan_id: UUID
    tm_plan_id: str
    name: str
    url: str
    image_url: str | None
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
    payment_id: UUID | None
    created_at: str
    updated_at: str
