"""Service layer handlers (business logic)."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

from adapters.ticketmaster import TicketmasterAdapter, ProviderError as TMProviderError
from adapters.payment import PaymentSimulatorAdapter, PaymentNotFoundError as PaymentAdapterNotFoundError

from domain.models import Order, Payment, Plan
from domain.value_objects import Money, Currency, TicketQuantity, Seat, AttendeeInfo
from domain.events import (
    OrderCreated, PaymentInitiated, PaymentConfirmed,
    PaymentFailed, OrderConfirmed, OrderCancelled
)
from domain.exceptions import (
    OrderNotFoundError,
    OrderInvalidStatusError,
    InsufficientInventoryError,
    SeatMismatchError,
    PaymentNotFoundError,
    PaymentDeclinedError,
    PlanNotFoundError,
    ValidationError,
    IdempotencyKeyUsedError,
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
from service_layer.fulfillment import FulfillOrderService
from service_layer.seat_holds import (
    acquire_seat_holds,
    release_seat_holds,
    check_payment_idempotency,
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
        fulfillment_service: FulfillOrderService,
        payment_adapter: PaymentSimulatorAdapter,
    ):
        self._uow = uow
        self._fulfillment = fulfillment_service
        self._payment = payment_adapter

    def handle_create_order(self, cmd: CreateOrderCommand) -> OrderCreatedResult:
        with self._uow:
            plan = self._get_plan_or_raise(cmd.plan_id)
            
            seats = self._parse_seats(cmd.seat_ids)
            quantity = TicketQuantity(cmd.quantity)
            total_amount = self._calculate_total(plan, seats, cmd.quantity)
            
            order = Order.create(
                plan_id=cmd.plan_id,
                quantity=quantity,
                total_amount=total_amount,
                attendee_info=cmd.attendee_info,
            )
            
            if seats:
                self._validate_seat_count(quantity, seats)
                self._acquire_seat_holds(cmd.plan_id, seats, order.order_id)
                order.reserve_seats(seats)
            
            payment, intent = self._create_payment_and_intent(order, total_amount)
            order.initiate_payment(payment.payment_id)
            
            self._save_order_and_payment(order, payment)
            
            return OrderCreatedResult(
                order_id=order.order_id,
                payment_intent_id=intent.id,
                client_secret=intent.client_secret,
                status=order.status,
            )

    def _get_plan_or_raise(self, plan_id: UUID) -> Plan:
        plan = self._uow.plans.get(plan_id)
        if not plan:
            raise PlanNotFoundError(str(plan_id))
        return plan

    def _parse_seats(self, seat_ids: Optional[List[SeatId]]) -> List[Seat]:
        seats = []
        if seat_ids:
            for seat_id in seat_ids:
                seats.append(seat_id.to_seat())
        return seats

    def _calculate_total(self, plan: Plan, seats: List[Seat], quantity: int) -> Money:
        if seats:
            return plan.calculate_total_for_seats(seats)
        return plan.min_price * quantity

    def _validate_seat_count(self, quantity: TicketQuantity, seats: List[Seat]) -> None:
        if len(seats) != quantity.value:
            raise SeatMismatchError(expected=quantity.value, got=len(seats))

    def _acquire_seat_holds(self, plan_id: UUID, seats: List[Seat], order_id: UUID) -> None:
        seat_ids = [f"{s.section}-{s.row}-{s.number}" for s in seats]
        if not acquire_seat_holds(self._fulfillment._tm.redis, plan_id, seat_ids, order_id):
            raise InsufficientInventoryError(
                str(plan_id),
                len(seats),
                len(seats) - 1,
            )

    def _create_payment_and_intent(self, order: Order, total_amount: Money) -> tuple:
        payment = Payment.create(
            order_id=order.order_id,
            amount=total_amount,
            provider="simulated",
            intent_id="",
        )
        intent = self._payment.create_payment_intent(
            amount=total_amount,
            currency=Currency.EUR,
            metadata={"order_id": str(order.order_id)},
        )
        payment.intent_id = intent.id
        return payment, intent

    def _save_order_and_payment(self, order: Order, payment: Payment) -> None:
        self._uow.orders.add(order)
        self._uow.payments.add(payment)

    def handle_confirm_payment(self, cmd: ConfirmPaymentCommand) -> PaymentConfirmedResult:
        with self._uow:
            order = self._uow.orders.get(cmd.order_id)
            if not order:
                raise OrderNotFoundError(str(cmd.order_id))

            payment = self._uow.payments.get_by_order_id(cmd.order_id)
            if not payment:
                raise PaymentNotFoundError(f"Payment for order {cmd.order_id} not found")

            # Verify payment confirmation idempotency key
            idempotency_key = getattr(cmd, 'idempotency_key', None) or f"payment_{payment.payment_id}"
            if not check_payment_idempotency(self._fulfillment._tm.redis, payment.payment_id, idempotency_key):
                raise IdempotencyKeyUsedError(idempotency_key)

            # Confirm payment with provider
            intent = self._payment.confirm_payment(cmd.payment_intent_id)
            if intent.status != "succeeded":
                payment.fail(intent.metadata.get("failure_reason", "Payment failed"))
                # Release seat holds on payment failure
                seat_ids = [f"{s.section}-{s.row}-{s.number}" for s in order.seats]
                release_seat_holds(self._fulfillment._tm.redis, order.plan_id, seat_ids, order.order_id)
                raise PaymentDeclinedError(str(payment.payment_id), intent.metadata.get("failure_reason", "Payment failed"))

            # Capture payment
            payment.capture(provider_ref=intent.metadata.get("captured_at", ""))
            order.confirm_payment()

            # Get plan to retrieve TM plan ID
            plan = self._uow.plans.get(order.plan_id)
            if not plan:
                raise PlanNotFoundError(str(order.plan_id))

            # Delegate TM fulfillment to separate service
            self._fulfillment.fulfill(order, plan)

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
                raise OrderNotFoundError(str(cmd.order_id))

            # Release seat holds before cancelling
            seat_ids = [f"{s.section}-{s.row}-{s.number}" for s in order.seats]
            release_seat_holds(self._fulfillment._tm.redis, order.plan_id, seat_ids, order.order_id)

            order.cancel(cmd.reason)
            self._uow.orders.add(order)

    def handle_refund_order(self, cmd: RefundOrderCommand) -> None:
        with self._uow:
            order = self._uow.orders.get(cmd.order_id)
            if not order:
                raise OrderNotFoundError(str(cmd.order_id))

            payment = self._uow.payments.get_by_order_id(cmd.order_id)
            if not payment:
                raise PaymentNotFoundError(f"Payment for order {cmd.order_id} not found")

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

        # If stale_only, only sync plans that haven't been synced in 24h
        stale_threshold_hours = 24

        while True:
            events = self._tm.search_plans(page=page, size=size)
            if not events:
                break

            for event in events:
                plan = Plan.from_ticketmaster(event)
                existing = self._uow.plans.get_by_tm_id(plan.tm_plan_id)
                
                # If stale_only, skip plans that were synced recently
                if cmd.stale_only and existing:
                    from datetime import timedelta, timezone
                    if existing.last_synced_at:
                        age = datetime.now(timezone.utc) - existing.last_synced_at
                        if age < timedelta(hours=stale_threshold_hours):
                            continue  # Skip this plan, it's fresh enough
                
                if existing:
                    self._tm.update_plan_from_ticketmaster(existing, event)
                else:
                    self._uow.plans.add(plan)
                synced += 1

            if len(events) < size:
                break
            page += 1

        return synced


class QueryHandler:
    def __init__(self, uow, tm_adapter: TicketmasterAdapter):
        self._uow = uow
        self._tm = tm_adapter

    def handle_search_plans(self, query: SearchPlansQuery) -> List:
        with self._uow:
            # Use TM adapter for search (full-text search, pagination handled by TM)
            events = self._tm.search_plans(
                query=query.query,
                lat=query.lat,
                lon=query.lon,
                radius_km=query.radius_km,
                date_from=query.date_from,
                date_to=query.date_to,
                min_price=query.min_price,
                max_price=query.max_price,
                page=0,  # TM handles pagination internally
                size=query.limit,
            )
            
            # Convert TM events to PlanSummary
            from service_layer.queries import PlanSearchResult
            return [PlanSearchResult(
                plan_id=UUID(e["id"]),  # This would need to match local plans
                name=e["name"],
                url=e["url"],
                image_url=e["images"][0]["url"] if e.get("images") else None,
                start_date=e["dates"]["start"]["dateTime"],
                start_time=e["dates"]["start"]["dateTime"][11:16],  # Extract time
                timezone=e["dates"]["timezone"],
                venue_name=e["_embedded"]["venues"][0]["name"],
                venue_city=e["_embedded"]["venues"][0]["city"]["name"],
                venue_state=e["_embedded"]["venues"][0]["state"]["name"],
                min_price=float(e.get("priceRanges", [{}])[0].get("min", 0)),
                max_price=float(e.get("priceRanges", [{}])[0].get("max", 0)),
                currency=e.get("priceRanges", [{}])[0].get("currency", "EUR"),
            ) for e in events]

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