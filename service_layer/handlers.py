"""Service layer handlers (business logic)."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

from adapters.ticketmaster import TicketmasterAdapter, PlanNotFoundError
from adapters.payment import PaymentSimulatorAdapter, PaymentNotFoundError

from domain.models import Order, Payment, Plan
from domain.value_objects import Money, Currency, TicketQuantity, Seat, AttendeeInfo
from domain.events import (
    OrderCreated, PaymentInitiated, PaymentConfirmed,
    PaymentFailed, OrderConfirmed, OrderCancelled
)

from service_layer.commands import (
    CreateOrderCommand, ConfirmPaymentCommand, CancelOrderCommand,
    RefundOrderCommand, ReserveSeatsCommand, SyncPlansCommand,
    OrderCreatedResult, PaymentConfirmedResult
)
from service_layer.queries import (
    SearchPlansQuery, GetOrderQuery, ListOrdersQuery, GetPlanQuery,
    PlanSearchResult, OrderStatusResult
)
from domain.repositories import (
    OrderRepository, PaymentRepository, PlanRepository,
    OrderReadRepository, PlanReadRepository,
    PlanSearchQuery
)


class OrderCommandHandler:
    def __init__(
        self,
        uow,
        tm_adapter: TicketmasterAdapter,
        payment_adapter: PaymentSimulatorAdapter,
    ):
        self._uow = uow
        self._tm = tm_adapter
        self._payment = payment_adapter

    def handle_create_order(self, cmd: CreateOrderCommand) -> OrderCreatedResult:
        with self._uow:
            # Get plan
            plan = self._uow.plans.get(cmd.plan_id)
            if not plan:
                raise ValueError(f"Plan {cmd.plan_id} not found")

            # Reserve seats (simplified - in reality, validate against plan seat map)
            seats = []
            if cmd.seat_ids:
                # In reality, would validate seats against plan
                for seat_id in cmd.seat_ids:
                    # Parse seat_id (format: section-row-number)
                    parts = seat_id.split("-")
                    if len(parts) == 3:
                        seats.append(Seat(section=parts[0], row=parts[1], number=parts[2]))

            quantity = TicketQuantity(cmd.quantity)
            total_amount = plan.min_price * cmd.quantity

            # Create order
            order = Order.create(
                plan_id=cmd.plan_id,
                quantity=quantity,
                total_amount=total_amount,
                attendee_info=cmd.attendee_info,
            )

            if seats:
                order.reserve_seats(seats)

            # Create payment
            payment = Payment.create(
                order_id=order.order_id,
                amount=total_amount,
                provider="simulated",
                intent_id="",  # Will be filled by payment adapter
            )

            # Create payment intent
            intent = self._payment.create_payment_intent(
                amount=total_amount,
                currency=Currency.EUR,
                metadata={"order_id": str(order.order_id)},
            )

            payment.intent_id = intent.id
            order.initiate_payment(payment.payment_id)

            # Save
            self._uow.orders.add(order)
            self._uow.payments.add(payment)

            return OrderCreatedResult(
                order_id=order.order_id,
                payment_intent_id=intent.id,
                client_secret=intent.client_secret,
                status=order.status,
            )

    def handle_confirm_payment(self, cmd: ConfirmPaymentCommand) -> PaymentConfirmedResult:
        with self._uow:
            order = self._uow.orders.get(cmd.order_id)
            if not order:
                raise ValueError(f"Order {cmd.order_id} not found")

            payment = self._uow.payments.get_by_order_id(cmd.order_id)
            if not payment:
                raise ValueError(f"Payment for order {cmd.order_id} not found")

            # Verify idempotency key (simplified - in reality check Redis)
            # For now, just proceed

            # Confirm payment with provider
            intent = self._payment.confirm_payment(cmd.payment_intent_id)
            if intent.status != "succeeded":
                payment.fail(intent.metadata.get("failure_reason", "Payment failed"))
                order.status = "PAYMENT_FAILED"  # Would need state transition
                raise ValueError("Payment failed")

            # Capture payment
            payment.capture(provider_ref=intent.metadata.get("captured_at", ""))
            order.confirm_payment()

            # Create TM offer (simulated)
            tm_order = self._tm.create_order(
                plan_id=str(order.plan_id),
                quantity=order.quantity.value,
                seat_ids=[f"{s.section}-{s.row}-{s.number}" for s in order.seats],
            )

            # Accept TM offer
            self._tm.accept_offer(tm_order["offer_id"])

            return PaymentConfirmedResult(
                order_id=order.order_id,
                payment_id=payment.payment_id,
                status=order.status,
                provider_ref=payment.provider_ref or "",
            )

    def handle_cancel_order(self, cmd: CancelOrderCommand) -> None:
        with self._uow:
            order = self._uow.orders.get(cmd.order_id)
            if not order:
                raise ValueError(f"Order {cmd.order_id} not found")

            order.cancel(cmd.reason)
            self._uow.orders.add(order)

    def handle_refund_order(self, cmd: RefundOrderCommand) -> None:
        with self._uow:
            order = self._uow.orders.get(cmd.order_id)
            if not order:
                raise ValueError(f"Order {cmd.order_id} not found")

            payment = self._uow.payments.get_by_order_id(cmd.order_id)
            if not payment:
                raise ValueError(f"Payment for order {cmd.order_id} not found")

            if cmd.amount:
                payment.refund(cmd.amount)
            else:
                payment.refund()

            order.refund()
            self._uow.orders.add(order)
            self._uow.payments.add(payment)


class PlanCommandHandler:
    def __init__(self, uow, tm_adapter: TicketmasterAdapter):
        self._uow = uow
        self._tm = tm_adapter

    def handle_sync_plans(self, cmd) -> int:
        """Sync plans from Ticketmaster. Returns count of synced plans."""
        synced = 0
        page = 0
        size = 100

        while True:
            events = self._tm.search_plans(page=page, size=size)
            if not events:
                break

            for event in events:
                plan = Plan.from_ticketmaster(event)
                existing = self._uow.plans.get_by_tm_id(plan.tm_plan_id)
                if existing:
                    existing.update_from_ticketmaster(event)
                else:
                    self._uow.plans.add(plan)
                synced += 1

            if len(events) < size:
                break
            page += 1

        return synced


class QueryHandler:
    def __init__(self, uow):
        self._uow = uow

    def handle_search_plans(self, query: SearchPlansQuery) -> List:
        with self._uow:
            plans = self._uow.plans_read.search_plans(PlanSearchQuery(
                query=query.query,
                lat=query.lat,
                lon=query.lon,
                radius_km=query.radius_km,
                date_from=query.date_from,
                date_to=query.date_to,
                min_price=query.min_price,
                max_price=query.max_price,
                cursor=query.cursor,
                limit=query.limit,
            ))
            return plans

    def handle_get_plan(self, query: GetPlanQuery):
        with self._uow:
            return self._uow.plans_read.get_plan(query.plan_id)

    def handle_get_order(self, query: GetOrderQuery):
        with self._uow:
            order = self._uow.orders_read.get_order_summary(query.order_id)
            return order

    def handle_list_orders(self, query: ListOrdersQuery):
        with self._uow:
            return self._uow.orders_read.list_orders(
                query.customer_email, query.cursor, query.limit
            )