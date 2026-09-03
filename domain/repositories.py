from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from domain.models import Order, Payment, Plan
from domain.value_objects import TicketQuantity
from dataclasses import dataclass


from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from dataclasses import dataclass, field

from domain.models import Order, Payment, Plan
from domain.value_objects import TicketQuantity


@dataclass
class PlanSearchQuery:
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
class PlanBase:
    """Base fields common to PlanSummary and PlanDetail."""
    plan_id: UUID
    name: str
    url: str
    image_url: Optional[str]
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
    seat_map: List[dict] = field(default_factory=list)


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
    seats: List[dict] = field(default_factory=list)
    payment_id: Optional[UUID] = None
    updated_at: str = ""


# Write Repository Ports
class OrderRepository(ABC):
    @abstractmethod
    def add(self, order: Order) -> None:
        pass

    @abstractmethod
    def get(self, order_id: UUID) -> Optional[Order]:
        pass

    @abstractmethod
    def get_by_payment_id(self, payment_id: UUID) -> Optional[Order]:
        pass


class PaymentRepository(ABC):
    @abstractmethod
    def add(self, payment: Payment) -> None:
        pass

    @abstractmethod
    def get(self, payment_id: UUID) -> Optional[Payment]:
        pass

    @abstractmethod
    def get_by_order_id(self, order_id: UUID) -> Optional[Payment]:
        pass


class PlanRepository(ABC):
    @abstractmethod
    def add(self, plan: Plan) -> None:
        pass

    @abstractmethod
    def get(self, plan_id: UUID) -> Optional[Plan]:
        pass

    @abstractmethod
    def get_by_tm_id(self, tm_plan_id: str) -> Optional[Plan]:
        pass


# Read Repository Ports
class OrderReadRepository(ABC):
    @abstractmethod
    def get_order_summary(self, order_id: UUID) -> Optional[OrderSummary]:
        pass

    @abstractmethod
    def list_orders(self, customer_email: str, cursor: Optional[str], limit: int) -> List[OrderSummary]:
        pass


class PlanReadRepository(ABC):
    @abstractmethod
    def search_plans(self, query: PlanSearchQuery) -> List[PlanSummary]:
        pass

    @abstractmethod
    def get_plan(self, plan_id: UUID) -> Optional[PlanDetail]:
        pass


# Search Port (for external provider search like Ticketmaster)
class PlanSearchPort(ABC):
    @abstractmethod
    def search_plans(
        self,
        query: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 0,
        size: int = 20,
    ) -> List[dict]:
        """Search for plans/events from external provider.
        
        Returns raw provider data (not domain models).
        """
        pass

    @abstractmethod
    def get_plan(self, plan_id: str) -> Optional[dict]:
        """Get single plan by ID from provider."""
        pass