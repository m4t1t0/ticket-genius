from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID

from domain.models import Order, Payment, Plan


@dataclass
class PlanSearchQuery:
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
class PlanBase:
    """Base fields common to PlanSummary and PlanDetail."""

    plan_id: UUID
    name: str
    url: str
    image_url: str | None
    start_date: str
    start_time: str
    timezone: str
    venue_name: str
    venue_city: str
    venue_state: str
    min_price: float
    max_price: float
    currency: str


@dataclass
class PlanSummary(PlanBase):
    pass


@dataclass
class PlanDetail(PlanBase):
    date_range: object
    seat_map: list[dict] = field(default_factory=list)


@dataclass
class OrderBase:
    """Base fields common to OrderSummary and OrderStatusDetail."""

    order_id: UUID
    plan_id: UUID
    plan_name: str
    status: str
    quantity: int
    total_amount: float
    currency: str
    created_at: str


@dataclass
class OrderSummary(OrderBase):
    pass


@dataclass
class OrderStatusDetail(OrderBase):
    seats: list[dict] = field(default_factory=list)
    payment_id: UUID | None = None
    updated_at: str = ""


# Write Repository Ports
class OrderRepository(ABC):
    @abstractmethod
    def add(self, order: Order) -> None:
        pass

    @abstractmethod
    def get(self, order_id: UUID) -> Order | None:
        pass

    @abstractmethod
    def get_by_payment_id(self, payment_id: UUID) -> Order | None:
        pass


class PaymentRepository(ABC):
    @abstractmethod
    def add(self, payment: Payment) -> None:
        pass

    @abstractmethod
    def get(self, payment_id: UUID) -> Payment | None:
        pass

    @abstractmethod
    def get_by_order_id(self, order_id: UUID) -> Payment | None:
        pass


class PlanRepository(ABC):
    @abstractmethod
    def add(self, plan: Plan) -> None:
        pass

    @abstractmethod
    def get(self, plan_id: UUID) -> Plan | None:
        pass

    @abstractmethod
    def get_by_tm_id(self, tm_plan_id: str) -> Plan | None:
        pass


# Read Repository Ports
class OrderReadRepository(ABC):
    @abstractmethod
    def get_order_summary(self, order_id: UUID) -> OrderSummary | None:
        pass

    @abstractmethod
    def list_orders(
        self, customer_email: str, cursor: str | None, limit: int
    ) -> list[OrderSummary]:
        pass


class PlanReadRepository(ABC):
    @abstractmethod
    def search_plans(self, query: PlanSearchQuery) -> list[PlanSummary]:
        pass

    @abstractmethod
    def get_plan(self, plan_id: UUID) -> PlanDetail | None:
        pass


# Search Port (for external provider search like Ticketmaster)
class PlanSearchPort(ABC):
    @abstractmethod
    def search_plans(
        self,
        query: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        page: int = 0,
        size: int = 20,
    ) -> list[dict]:
        """Search for plans/events from external provider.

        Returns raw provider data (not domain models).
        """

    @abstractmethod
    def get_plan(self, plan_id: str) -> dict | None:
        """Get single plan by ID from provider."""
