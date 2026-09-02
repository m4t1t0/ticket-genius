from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict
from uuid import UUID, uuid4

from domain.value_objects import AttendeeInfo, Money


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None


@dataclass(frozen=True, slots=True)
class OrderCreated:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    order_id: UUID = field(default_factory=uuid4)
    plan_id: UUID = field(default_factory=uuid4)
    quantity: int = 0
    total_amount: Money = field(default_factory=lambda: Money(amount=0))
    attendee_info: Optional[AttendeeInfo] = None


@dataclass(frozen=True, slots=True)
class PaymentInitiated:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    order_id: UUID = field(default_factory=uuid4)
    payment_id: UUID = field(default_factory=uuid4)
    provider: str = ""
    intent_id: str = ""


@dataclass(frozen=True, slots=True)
class PaymentConfirmed:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    order_id: UUID = field(default_factory=uuid4)
    payment_id: UUID = field(default_factory=uuid4)
    provider_ref: str = ""


@dataclass(frozen=True, slots=True)
class PaymentFailed:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    order_id: UUID = field(default_factory=uuid4)
    payment_id: UUID = field(default_factory=uuid4)
    reason: str = ""


@dataclass(frozen=True, slots=True)
class OrderConfirmed:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    order_id: UUID = field(default_factory=uuid4)
    tickets: List[Dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class OrderCancelled:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    order_id: UUID = field(default_factory=uuid4)
    reason: str = ""