from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from domain.models import Order, Payment, Plan
from domain.value_objects import TicketQuantity
from dataclasses import dataclass


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
class PlanSummary:
    plan_id: UUID
    tm_plan_id: str
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
    seat_map: List[dict]


@dataclass
class OrderSummary:
    order_id: UUID
    plan_id: UUID
    plan_name: str
    status: str
    quantity: int
    total_amount: float
    currency: str
    created_at: str


@dataclass
class OrderStatusDetail:
    order_id: UUID
    plan_id: UUID
    plan_name: str
    status: str
    quantity: int
    total_amount: float
    currency: str
    seats: List[dict]
    payment_id: Optional[UUID]
    created_at: str
    updated_at: str


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