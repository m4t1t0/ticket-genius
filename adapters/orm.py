"""SQLAlchemy Imperative Mapping for domain models."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from sqlalchemy import (
    Table, Column, String, Integer, DateTime, ForeignKey, Index,
    UniqueConstraint, Text, JSON, Enum as SQLEnum, Numeric, TypeDecorator, CHAR
)
from sqlalchemy.orm import registry, relationship, composite
from sqlalchemy.schema import FetchedValue


class UUIDType(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type when available, otherwise falls back to CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, UUID):
            return value
        return UUID(value)

from domain.models import Order, Payment, Plan
from domain.value_objects import Money, Seat, DateRange, TicketQuantity, AttendeeInfo, Currency
from domain.events import OrderCreated, PaymentInitiated, PaymentConfirmed, PaymentFailed, OrderConfirmed, OrderCancelled

mapper_registry = registry()

# --- Tables ---

attendees_table = Table(
    "attendees",
    mapper_registry.metadata,
    Column("id", UUIDType(), primary_key=True),
    Column("order_id", UUIDType(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("email", String(255), nullable=False),
    Column("phone", String(50), nullable=True),
    Index("ix_attendees_order_id", "order_id"),
)

seats_table = Table(
    "seats",
    mapper_registry.metadata,
    Column("id", UUIDType(), primary_key=True),
    Column("order_id", UUIDType(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    Column("section", String(50), nullable=False),
    Column("row", String(50), nullable=False),
    Column("number", String(50), nullable=False),
    Index("ix_seats_order_id", "order_id"),
)

orders_table = Table(
    "orders",
    mapper_registry.metadata,
    Column("id", UUIDType(), primary_key=True),
    Column("plan_id", UUIDType(), ForeignKey("plans.id"), nullable=False),
    Column("quantity_value", Integer, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", SQLEnum(Currency, name="currency_enum", values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=Currency.EUR),
    Column("status", String(30), nullable=False, default="PENDING"),
    Column("payment_id", UUIDType(), ForeignKey("payments.id"), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)),
    Index("ix_orders_plan_id", "plan_id"),
    Index("ix_orders_status", "status"),
    Index("ix_orders_payment_id", "payment_id"),
)

payments_table = Table(
    "payments",
    mapper_registry.metadata,
    Column("id", UUIDType(), primary_key=True),
    Column("order_id", UUIDType(), ForeignKey("orders.id"), nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", SQLEnum(Currency, name="currency_enum"), nullable=False, default=Currency.EUR),
    Column("provider", String(50), nullable=False),
    Column("status", String(30), nullable=False, default="CREATED"),
    Column("provider_ref", String(255), nullable=True),
    Column("intent_id", String(255), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)),
    Index("ix_payments_order_id", "order_id"),
    Index("ix_payments_status", "status"),
    UniqueConstraint("order_id", name="uq_payment_order"),
)

plans_table = Table(
    "plans",
    mapper_registry.metadata,
    Column("id", UUIDType(), primary_key=True),
    Column("tm_plan_id", String(100), nullable=False, unique=True),
    Column("name", String(500), nullable=False),
    Column("url", String(1000), nullable=False),
    Column("image_url", String(1000), nullable=True),
    Column("start_date", DateTime(timezone=True), nullable=False),
    Column("end_date", DateTime(timezone=True), nullable=False),
    Column("timezone", String(50), nullable=False),
    Column("venue_name", String(255), nullable=False),
    Column("venue_city", String(100), nullable=False),
    Column("venue_state", String(100), nullable=False),
    Column("min_price_cents", Integer, nullable=False),
    Column("max_price_cents", Integer, nullable=False),
    Column("currency", SQLEnum(Currency, name="currency_enum"), nullable=False, default=Currency.EUR),
    Column("last_synced_at", DateTime(timezone=True), nullable=False),
    Column("tm_last_modified", DateTime(timezone=True), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)),
    Index("ix_plans_tm_plan_id", "tm_plan_id", unique=True),
    Index("ix_plans_date_range", "start_date", "end_date"),
    Index("ix_plans_venue_city", "venue_city"),
)

outbox_table = Table(
    "outbox",
    mapper_registry.metadata,
    Column("id", UUIDType(), primary_key=True),
    Column("aggregate_id", UUIDType(), nullable=False),
    Column("aggregate_type", String(50), nullable=False),
    Column("event_type", String(100), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("processed_at", DateTime(timezone=True), nullable=True),
    Column("retry_count", Integer, nullable=False, default=0),
    Index("ix_outbox_unprocessed", "processed_at", postgresql_where=(Column("processed_at").is_(None))),
    Index("ix_outbox_aggregate", "aggregate_id", "aggregate_type"),
)

# --- Mappers ---

def _money_composite(amount_cents_col, currency_col):
    return composite(
        lambda cents, curr: Money(amount=Decimal(cents) / 100, currency=curr),
        amount_cents_col,
        currency_col,
    )


def _seat_composite(section_col, row_col, number_col):
    return composite(
        Seat,
        section_col,
        row_col,
        number_col,
    )


def _date_range_composite(start_col, end_col, timezone_col):
    return composite(
        DateRange,
        start_col,
        end_col,
        timezone_col,
    )


def _ticket_quantity_composite(value_col):
    return composite(
        TicketQuantity,
        value_col,
    )


def _attendee_info_composite(name_col, email_col, phone_col):
    return composite(
        AttendeeInfo,
        name_col,
        email_col,
        phone_col,
    )


# Order mapper
mapper_registry.map_imperatively(
    Order,
    orders_table,
    properties={
        "order_id": orders_table.c.id,
        "plan_id": orders_table.c.plan_id,
        "quantity": _ticket_quantity_composite(orders_table.c.quantity_value),
        "total_amount": _money_composite(orders_table.c.amount_cents, orders_table.c.currency),
        "status": orders_table.c.status,
        "payment_id": orders_table.c.payment_id,
        "version": orders_table.c.version,
        "seats": relationship(
            Seat,
            backref="order",
            cascade="all, delete-orphan",
            collection_class=list,
        ),
        "attendee_info": relationship(
            AttendeeInfo,
            backref="order",
            cascade="all, delete-orphan",
            collection_class=list,
            uselist=False,
        ),
    },
)

# Payment mapper
mapper_registry.map_imperatively(
    Payment,
    payments_table,
    properties={
        "payment_id": payments_table.c.id,
        "order_id": payments_table.c.order_id,
        "amount": _money_composite(payments_table.c.amount_cents, payments_table.c.currency),
        "provider": payments_table.c.provider,
        "status": payments_table.c.status,
        "provider_ref": payments_table.c.provider_ref,
        "intent_id": payments_table.c.intent_id,
        "version": payments_table.c.version,
    },
)

# Plan mapper
mapper_registry.map_imperatively(
    Plan,
    plans_table,
    properties={
        "plan_id": plans_table.c.id,
        "tm_plan_id": plans_table.c.tm_plan_id,
        "name": plans_table.c.name,
        "url": plans_table.c.url,
        "image_url": plans_table.c.image_url,
        "date_range": _date_range_composite(
            plans_table.c.start_date,
            plans_table.c.end_date,
            plans_table.c.timezone,
        ),
        "venue_name": plans_table.c.venue_name,
        "venue_city": plans_table.c.venue_city,
        "venue_state": plans_table.c.venue_state,
        "min_price": _money_composite(plans_table.c.min_price_cents, plans_table.c.currency),
        "max_price": _money_composite(plans_table.c.max_price_cents, plans_table.c.currency),
        "last_synced_at": plans_table.c.last_synced_at,
        "tm_last_modified": plans_table.c.tm_last_modified,
        "version": plans_table.c.version,
    },
)

# AttendeeInfo mapper
mapper_registry.map_imperatively(
    AttendeeInfo,
    attendees_table,
    properties={
        "id": attendees_table.c.id,
        "name": attendees_table.c.name,
        "email": attendees_table.c.email,
        "phone": attendees_table.c.phone,
    },
)

# Seat mapper
mapper_registry.map_imperatively(
    Seat,
    seats_table,
    properties={
        "id": seats_table.c.id,
        "section": seats_table.c.section,
        "row": seats_table.c.row,
        "number": seats_table.c.number,
    },
)

# Outbox mapper
@mapper_registry.mapped
class OutboxEvent:
    __table__ = outbox_table

    def __init__(self, aggregate_id, aggregate_type, event_type, payload):
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.event_type = event_type
        self.payload = payload


def start_mappers():
    """Initialize all mappers. Call once at startup."""
    pass  # Mappers are registered via decorators and map_imperatively calls


if __name__ == "__main__":
    # Quick test
    from sqlalchemy import create_engine
    engine = create_engine("postgresql://localhost/test", echo=True)
    mapper_registry.metadata.create_all(engine)
    print("Tables created successfully")