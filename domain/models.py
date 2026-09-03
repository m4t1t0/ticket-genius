from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from domain.events import (
    DomainEvent, OrderCreated, PaymentInitiated, PaymentConfirmed,
    PaymentFailed, OrderConfirmed, OrderCancelled
)
from domain.value_objects import AttendeeInfo, Money, Seat, TicketQuantity, Currency


class AggregateRoot:
    def __init__(self):
        self._domain_events: List[DomainEvent] = []

    @property
    def domain_events(self) -> List[DomainEvent]:
        return self._domain_events

    def add_domain_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def clear_domain_events(self) -> None:
        self._domain_events.clear()


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SEATS_RESERVED = "SEATS_RESERVED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAID = "PAID"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


@dataclass
class Order(AggregateRoot):
    order_id: UUID
    plan_id: UUID
    quantity: TicketQuantity
    total_amount: Money
    attendee_info: AttendeeInfo
    status: OrderStatus = OrderStatus.PENDING
    payment_id: Optional[UUID] = None
    seats: List[Seat] = field(default_factory=list)
    version: int = 1

    def __post_init__(self):
        if not isinstance(self.status, OrderStatus):
            raise ValueError(f"Invalid order status: {self.status}")
        # Initialize domain events list for dataclass inheritance
        if not hasattr(self, '_domain_events'):
            self._domain_events = []

    @classmethod
    def create(
        cls,
        plan_id: UUID,
        quantity: TicketQuantity,
        total_amount: Money,
        attendee_info: AttendeeInfo,
    ) -> "Order":
        order = cls(
            order_id=uuid4(),
            plan_id=plan_id,
            quantity=quantity,
            total_amount=total_amount,
            attendee_info=attendee_info,
        )
        order.add_domain_event(
            OrderCreated(
                order_id=order.order_id,
                plan_id=plan_id,
                quantity=quantity.value,
                total_amount=total_amount,
                attendee_name=attendee_info.name,
                attendee_email=attendee_info.email,
                attendee_phone=attendee_info.phone,
            )
        )
        return order

    def reserve_seats(self, seats: List[Seat]) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot reserve seats in status {self.status}")
        if len(seats) != self.quantity.value:
            raise ValueError(f"Expected {self.quantity.value} seats, got {len(seats)}")
        self.seats = seats
        self.status = OrderStatus.SEATS_RESERVED
        self.version += 1

    def initiate_payment(self, payment_id: UUID) -> None:
        if self.status != OrderStatus.SEATS_RESERVED:
            raise ValueError(f"Cannot initiate payment in status {self.status}")
        self.payment_id = payment_id
        self.status = OrderStatus.PAYMENT_INITIATED
        self.version += 1

    def confirm_payment(self) -> None:
        if self.status != OrderStatus.PAYMENT_INITIATED:
            raise ValueError(f"Cannot confirm payment in status {self.status}")
        self.status = OrderStatus.PAID
        self.version += 1

    def fulfill(self, tickets: List[dict]) -> None:
        if self.status != OrderStatus.PAID:
            raise ValueError(f"Cannot fulfill in status {self.status}")
        self.status = OrderStatus.FULFILLED
        self.version += 1
        self.add_domain_event(
            OrderConfirmed(
                order_id=self.order_id,
                tickets=tickets,
            )
        )

    def cancel(self, reason: str) -> None:
        if self.status not in (OrderStatus.PENDING, OrderStatus.SEATS_RESERVED, OrderStatus.PAYMENT_INITIATED):
            raise ValueError(f"Cannot cancel in status {self.status}")
        self.status = OrderStatus.CANCELLED
        self.version += 1
        self.add_domain_event(
            OrderCancelled(
                order_id=self.order_id,
                reason=reason,
            )
        )

    def refund(self) -> None:
        if self.status not in (OrderStatus.PAID, OrderStatus.FULFILLED):
            raise ValueError(f"Cannot refund in status {self.status}")
        self.status = OrderStatus.REFUNDED
        self.version += 1

    def __repr__(self) -> str:
        return f"Order(id={self.order_id}, plan={self.plan_id}, status={self.status}, version={self.version})"


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


@dataclass
class Payment(AggregateRoot):
    payment_id: UUID
    order_id: UUID
    amount: Money
    provider: str
    status: PaymentStatus = PaymentStatus.CREATED
    provider_ref: Optional[str] = None
    intent_id: Optional[str] = None
    version: int = 1

    def __post_init__(self):
        if not isinstance(self.status, PaymentStatus):
            raise ValueError(f"Invalid payment status: {self.status}")
        if not hasattr(self, '_domain_events'):
            self._domain_events = []

    @classmethod
    def create(
        cls,
        order_id: UUID,
        amount: Money,
        provider: str,
        intent_id: str,
    ) -> "Payment":
        payment = cls(
            payment_id=uuid4(),
            order_id=order_id,
            amount=amount,
            provider=provider,
            intent_id=intent_id,
        )
        return payment

    def authorize(self) -> None:
        if self.status != PaymentStatus.CREATED:
            raise ValueError(f"Cannot authorize in status {self.status}")
        self.status = PaymentStatus.AUTHORIZED
        self.version += 1

    def capture(self, provider_ref: str) -> None:
        if self.status != PaymentStatus.AUTHORIZED:
            raise ValueError(f"Cannot capture in status {self.status}")
        self.provider_ref = provider_ref
        self.status = PaymentStatus.CAPTURED
        self.version += 1

    def fail(self, reason: str) -> None:
        if self.status not in (PaymentStatus.CREATED, PaymentStatus.AUTHORIZED):
            raise ValueError(f"Cannot fail in status {self.status}")
        self.status = PaymentStatus.FAILED
        self.version += 1

    def refund(self, amount: Optional[Money] = None) -> None:
        if self.status != PaymentStatus.CAPTURED:
            raise ValueError(f"Cannot refund in status {self.status}")
        if amount is None or amount.amount >= self.amount.amount:
            self.status = PaymentStatus.REFUNDED
        else:
            self.status = PaymentStatus.PARTIALLY_REFUNDED
        self.version += 1

    def __repr__(self) -> str:
        return f"Payment(id={self.payment_id}, order={self.order_id}, status={self.status}, amount={self.amount})"


@dataclass
class Plan(AggregateRoot):
    plan_id: UUID
    _tm_plan_id: str  # Private: used for ORM mapping, not part of domain API
    name: str
    url: str
    image_url: Optional[str]
    date_range: object  # DateRange from value_objects
    venue_name: str
    venue_city: str
    venue_state: str
    min_price: Money
    max_price: Money
    last_synced_at: datetime
    tm_last_modified: datetime
    version: int = 1
    seat_prices_json: dict = field(default_factory=dict)  # JSON column storage

    def __post_init__(self):
        if not self._tm_plan_id:
            raise ValueError("tm_plan_id is required")
        if not hasattr(self, '_domain_events'):
            self._domain_events = []

    @property
    def tm_plan_id(self) -> str:
        """Internal accessor for repository/ORM mapping."""
        return self._tm_plan_id

    @property
    def seat_prices(self) -> dict:
        """Get seat prices as dict of section -> Money.
        
        Converts from JSON storage format (price_cents) to domain format (Money).
        """
        result = {}
        for section, price_cents in self.seat_prices_json.items():
            result[section] = Money(amount=Decimal(price_cents) / 100, currency=Currency.EUR)
        return result

    @seat_prices.setter
    def seat_prices(self, value: dict):
        """Set seat prices from domain format (Money) to JSON storage format (price_cents)."""
        self.seat_prices_json = {
            section: int(price.amount * 100) for section, price in value.items()
        }

    def get_seat_price(self, seat: Seat) -> Money:
        """Get price for a specific seat.
        
        Falls back to min_price if no specific section pricing available.
        """
        section_price = self.seat_prices.get(seat.section)
        if section_price:
            return section_price
        return self.min_price

    def calculate_total_for_seats(self, seats: List[Seat]) -> Money:
        """Calculate total price for a list of seats."""
        total = Money(Decimal('0'), self.min_price.currency)
        for seat in seats:
            total = total + self.get_seat_price(seat)
        return total

    @classmethod
    def from_ticketmaster(cls, tm_data: dict) -> "Plan":
        from domain.value_objects import DateRange, Money, Currency
        from datetime import datetime
        from decimal import Decimal
        from uuid import UUID, uuid5, NAMESPACE_URL

        # Parse TM date
        start_str = tm_data["dates"]["start"]["dateTime"]
        end_str = tm_data["dates"].get("end", {}).get("dateTime", start_str)
        tz = tm_data["dates"]["timezone"]

        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        price_range = tm_data.get("priceRanges", [{}])[0]
        min_price = Money(Decimal(str(price_range.get("min", 0))), Currency.EUR)
        max_price = Money(Decimal(str(price_range.get("max", 0))), Currency.EUR)

        # Deterministic UUID based on TM plan ID for idempotent upsert
        tm_plan_id = tm_data["id"]
        plan_id = uuid5(NAMESPACE_URL, f"ticketmaster.com/events/{tm_plan_id}")

        return cls(
            plan_id=plan_id,
            _tm_plan_id=tm_plan_id,
            name=tm_data["name"],
            url=tm_data["url"],
            image_url=tm_data["images"][0]["url"] if tm_data.get("images") else None,
            date_range=DateRange(start=start, end=end, timezone=tz),
            venue_name=tm_data["_embedded"]["venues"][0]["name"],
            venue_city=tm_data["_embedded"]["venues"][0]["city"]["name"],
            venue_state=tm_data["_embedded"]["venues"][0]["state"]["name"],
            min_price=min_price,
            max_price=max_price,
            seat_prices_json={},  # TM doesn't provide per-section pricing
            last_synced_at=datetime.now(timezone.utc),
            tm_last_modified=datetime.fromisoformat(tm_data["lastUpdated"].replace("Z", "+00:00")),
        )

    

    def __repr__(self) -> str:
        return f"Plan(id={self.plan_id}, tm_id={self._tm_plan_id}, name={self.name}, version={self.version})"