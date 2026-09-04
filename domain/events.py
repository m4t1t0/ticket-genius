from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class OrderCreated:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    order_id: UUID = field(default_factory=uuid4)
    plan_id: UUID = field(default_factory=uuid4)
    quantity: int = 0
    total_amount: Money = field(default_factory=lambda: Money(amount=0))
    # Attendee info as primitives for serialization
    attendee_name: str = ""
    attendee_email: str = ""
    attendee_phone: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentInitiated:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    order_id: UUID = field(default_factory=uuid4)
    payment_id: UUID = field(default_factory=uuid4)
    provider: str = ""
    intent_id: str = ""


@dataclass(frozen=True, slots=True)
class PaymentConfirmed:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    order_id: UUID = field(default_factory=uuid4)
    payment_id: UUID = field(default_factory=uuid4)
    provider_ref: str = ""


@dataclass(frozen=True, slots=True)
class PaymentFailed:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    order_id: UUID = field(default_factory=uuid4)
    payment_id: UUID = field(default_factory=uuid4)
    reason: str = ""


@dataclass(frozen=True, slots=True)
class OrderConfirmed:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    order_id: UUID = field(default_factory=uuid4)
    tickets: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class OrderCancelled:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    order_id: UUID = field(default_factory=uuid4)
    reason: str = ""
