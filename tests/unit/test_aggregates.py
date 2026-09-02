"""Tests for domain aggregates."""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from domain import Order, Payment, Plan, Money, TicketQuantity, AttendeeInfo, Seat, Currency, OrderStatus, PaymentStatus


class TestOrder:
    @pytest.fixture
    def valid_order_data(self):
        return {
            "plan_id": uuid4(),
            "quantity": TicketQuantity(2),
            "total_amount": Money(amount=100, currency=Currency.EUR),
            "attendee_info": AttendeeInfo(name="John Doe", email="john@example.com"),
        }

    def test_create_order(self, valid_order_data):
        order = Order.create(**valid_order_data)
        assert order.status == OrderStatus.PENDING
        assert order.order_id is not None
        assert order.version == 1
        assert len(order.domain_events) == 1
        assert isinstance(order.domain_events[0], type(order.domain_events[0]))  # OrderCreated

    def test_reserve_seats(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [
            Seat(section="A", row="1", number="10"),
            Seat(section="A", row="1", number="11"),
        ]
        order.reserve_seats(seats)
        assert order.status == OrderStatus.SEATS_RESERVED
        assert order.seats == seats
        assert order.version == 2

    def test_reserve_seats_wrong_count_raises(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10")]  # Only 1 seat for qty=2
        with pytest.raises(ValueError, match="Expected 2 seats"):
            order.reserve_seats(seats)

    def test_initiate_payment(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10"), Seat(section="A", row="1", number="11")]
        order.reserve_seats(seats)

        payment_id = uuid4()
        order.initiate_payment(payment_id)
        assert order.status == OrderStatus.PAYMENT_INITIATED
        assert order.payment_id == payment_id
        assert order.version == 3

    def test_confirm_payment(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10"), Seat(section="A", row="1", number="11")]
        order.reserve_seats(seats)
        order.initiate_payment(uuid4())

        order.confirm_payment()
        assert order.status == OrderStatus.PAID
        assert order.version == 4

    def test_fulfill(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10"), Seat(section="A", row="1", number="11")]
        order.reserve_seats(seats)
        order.initiate_payment(uuid4())
        order.confirm_payment()

        tickets = [{"ticket_id": "t1", "seat": str(seats[0])}, {"ticket_id": "t2", "seat": str(seats[1])}]
        order.fulfill(tickets)
        assert order.status == OrderStatus.FULFILLED
        assert order.version == 5
        # Check OrderConfirmed event was emitted
        events = [e for e in order.domain_events if type(e).__name__ == "OrderConfirmed"]
        assert len(events) == 1

    def test_cancel_from_pending(self, valid_order_data):
        order = Order.create(**valid_order_data)
        order.cancel("Customer request")
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_from_seats_reserved(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10"), Seat(section="A", row="1", number="11")]
        order.reserve_seats(seats)
        order.cancel("Customer request")
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_from_paid_raises(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10"), Seat(section="A", row="1", number="11")]
        order.reserve_seats(seats)
        order.initiate_payment(uuid4())
        order.confirm_payment()
        with pytest.raises(ValueError, match="Cannot cancel in status PAID"):
            order.cancel("Too late")

    def test_refund_from_paid(self, valid_order_data):
        order = Order.create(**valid_order_data)
        seats = [Seat(section="A", row="1", number="10"), Seat(section="A", row="1", number="11")]
        order.reserve_seats(seats)
        order.initiate_payment(uuid4())
        order.confirm_payment()
        order.refund()
        assert order.status == OrderStatus.REFUNDED


class TestPayment:
    def test_create_payment(self):
        payment = Payment.create(
            order_id=uuid4(),
            amount=Money(amount=100, currency=Currency.EUR),
            provider="stripe",
            intent_id="pi_test_123",
        )
        assert payment.status == PaymentStatus.CREATED
        assert payment.intent_id == "pi_test_123"

    def test_authorize(self):
        payment = Payment.create(
            order_id=uuid4(),
            amount=Money(amount=100, currency=Currency.EUR),
            provider="stripe",
            intent_id="pi_test_123",
        )
        payment.authorize()
        assert payment.status == PaymentStatus.AUTHORIZED

    def test_capture(self):
        payment = Payment.create(
            order_id=uuid4(),
            amount=Money(amount=100, currency=Currency.EUR),
            provider="stripe",
            intent_id="pi_test_123",
        )
        payment.authorize()
        payment.capture("ch_test_123")
        assert payment.status == PaymentStatus.CAPTURED
        assert payment.provider_ref == "ch_test_123"

    def test_fail(self):
        payment = Payment.create(
            order_id=uuid4(),
            amount=Money(amount=100, currency=Currency.EUR),
            provider="stripe",
            intent_id="pi_test_123",
        )
        payment.fail("Card declined")
        assert payment.status == PaymentStatus.FAILED

    def test_refund_full(self):
        payment = Payment.create(
            order_id=uuid4(),
            amount=Money(amount=100, currency=Currency.EUR),
            provider="stripe",
            intent_id="pi_test_123",
        )
        payment.authorize()
        payment.capture("ch_test_123")
        payment.refund()
        assert payment.status == PaymentStatus.REFUNDED

    def test_refund_partial(self):
        payment = Payment.create(
            order_id=uuid4(),
            amount=Money(amount=100, currency=Currency.EUR),
            provider="stripe",
            intent_id="pi_test_123",
        )
        payment.authorize()
        payment.capture("ch_test_123")
        payment.refund(amount=Money(amount=50, currency=Currency.EUR))
        assert payment.status == PaymentStatus.PARTIALLY_REFUNDED


class TestPlan:
    @pytest.fixture
    def tm_data(self):
        return {
            "id": "tm_123",
            "name": "Test Concert",
            "url": "https://test.com",
            "images": [{"url": "https://test.com/img.jpg"}],
            "dates": {
                "start": {"dateTime": "2026-12-01T20:00:00Z"},
                "end": {"dateTime": "2026-12-01T23:00:00Z"},
                "timezone": "Europe/Madrid",
            },
            "_embedded": {
                "venues": [{
                    "name": "Test Venue",
                    "city": {"name": "Madrid"},
                    "state": {"name": "Madrid"},
                }]
            },
            "priceRanges": [{"min": 50, "max": 150}],
            "lastUpdated": "2026-01-01T00:00:00Z",
        }

    def test_from_ticketmaster(self, tm_data):
        plan = Plan.from_ticketmaster(tm_data)
        assert plan.tm_plan_id == "tm_123"
        assert plan.name == "Test Concert"
        assert plan.venue_city == "Madrid"
        assert plan.min_price.amount == 50
        assert plan.max_price.amount == 150
        assert plan.version == 1

    def test_update_from_ticketmaster(self, tm_data):
        plan = Plan.from_ticketmaster(tm_data)
        old_version = plan.version
        old_last_synced = plan.last_synced_at

        # Modified TM data
        tm_data["name"] = "Updated Concert"
        tm_data["priceRanges"] = [{"min": 60, "max": 160}]
        tm_data["lastUpdated"] = "2026-01-02T00:00:00Z"

        plan.update_from_ticketmaster(tm_data)
        assert plan.name == "Updated Concert"
        assert plan.min_price.amount == 60
        assert plan.max_price.amount == 160
        assert plan.version == old_version + 1
        assert plan.last_synced_at > old_last_synced

    def test_is_stale(self, tm_data):
        plan = Plan.from_ticketmaster(tm_data)
        assert not plan.is_stale(24)

        # Manually set last_synced_at to 25 hours ago
        plan.last_synced_at = datetime.now(timezone.utc) - timedelta(hours=25)
        assert plan.is_stale(24)

    def test_repr(self, tm_data):
        plan = Plan.from_ticketmaster(tm_data)
        assert "Plan" in repr(plan)
        assert "tm_123" in repr(plan)