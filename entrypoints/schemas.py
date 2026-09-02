"""Pydantic schemas for request/response validation."""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict


class MoneySchema(BaseModel):
    amount: Decimal
    currency: str = "EUR"


class SeatSchema(BaseModel):
    section: str
    row: str
    number: str


class AttendeeInfoSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = None


# Request schemas
class CreateOrderRequest(BaseModel):
    plan_id: UUID
    quantity: int = Field(..., ge=1, le=8)
    attendee_info: AttendeeInfoSchema
    seat_ids: Optional[List[str]] = None


class ConfirmPaymentRequest(BaseModel):
    payment_intent_id: str
    idempotency_key: str


class CancelOrderRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class RefundOrderRequest(BaseModel):
    amount: Optional[MoneySchema] = None
    reason: str = "Customer request"


class SearchPlansRequest(BaseModel):
    query: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: Optional[int] = Field(None, ge=1, le=500)
    date_from: Optional[str] = None  # ISO format
    date_to: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    cursor: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)


# Response schemas
class PlanSummaryResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class PlanDetailResponse(BaseModel):
    plan_id: UUID
    tm_plan_id: str
    name: str
    url: str
    image_url: Optional[str]
    date_range: dict
    venue_name: str
    venue_city: str
    venue_state: str
    min_price: float
    max_price: float
    currency: str
    seat_map: List[dict]

    model_config = ConfigDict(from_attributes=True)


class OrderCreatedResponse(BaseModel):
    order_id: UUID
    payment_intent_id: str
    client_secret: str
    status: str


class PaymentConfirmedResponse(BaseModel):
    order_id: UUID
    payment_id: UUID
    status: str
    provider_ref: str


class OrderStatusResponse(BaseModel):
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


class PlanSearchResponse(BaseModel):
    plans: List[PlanSummaryResponse]
    cursor: Optional[str]
    has_more: bool


class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None


class SyncPlansResponse(BaseModel):
    synced_count: int
    message: str