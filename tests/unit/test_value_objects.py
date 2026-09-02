"""Tests for domain value objects."""
import pytest
from decimal import Decimal
from domain.value_objects import Money, Currency, Seat, DateRange, TicketQuantity, AttendeeInfo


class TestMoney:
    def test_create_with_int(self):
        money = Money(amount=100, currency=Currency.EUR)
        assert money.amount == Decimal("100")
        assert money.currency == Currency.EUR

    def test_create_with_decimal(self):
        money = Money(amount=Decimal("99.99"), currency=Currency.USD)
        assert money.amount == Decimal("99.99")

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            Money(amount=-10, currency=Currency.EUR)

    def test_too_many_decimals_raises(self):
        with pytest.raises(ValueError, match="more than 2 decimal places"):
            Money(amount=Decimal("10.123"), currency=Currency.EUR)

    def test_add_same_currency(self):
        m1 = Money(amount=50, currency=Currency.EUR)
        m2 = Money(amount=30, currency=Currency.EUR)
        result = m1 + m2
        assert result.amount == Decimal("80")

    def test_add_different_currency_raises(self):
        m1 = Money(amount=50, currency=Currency.EUR)
        m2 = Money(amount=30, currency=Currency.USD)
        with pytest.raises(ValueError, match="different currencies"):
            m1 + m2

    def test_sub_same_currency(self):
        m1 = Money(amount=50, currency=Currency.EUR)
        m2 = Money(amount=30, currency=Currency.EUR)
        result = m1 - m2
        assert result.amount == Decimal("20")

    def test_mul(self):
        m = Money(amount=10, currency=Currency.EUR)
        result = m * 3
        assert result.amount == Decimal("30")

    def test_repr(self):
        money = Money(amount=100, currency=Currency.EUR)
        assert repr(money) == "Money(100.00 EUR)"


class TestSeat:
    def test_create_valid(self):
        seat = Seat(section="A", row="1", number="10")
        assert seat.section == "A"
        assert seat.row == "1"
        assert seat.number == "10"

    def test_empty_section_raises(self):
        with pytest.raises(ValueError, match="required"):
            Seat(section="", row="1", number="10")

    def test_repr(self):
        seat = Seat(section="A", row="1", number="10")
        assert "Seat" in repr(seat)


class TestDateRange:
    def test_create_valid(self):
        from datetime import datetime, timezone
        start = datetime(2026, 1, 1, 20, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        dr = DateRange(start=start, end=end, timezone="Europe/Madrid")
        assert dr.timezone == "Europe/Madrid"

    def test_start_after_end_raises(self):
        from datetime import datetime, timezone
        start = datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 20, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="start must be before end"):
            DateRange(start=start, end=end, timezone="UTC")

    def test_empty_timezone_raises(self):
        from datetime import datetime, timezone
        start = datetime(2026, 1, 1, 20, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="timezone is required"):
            DateRange(start=start, end=end, timezone="")


class TestTicketQuantity:
    def test_valid_range(self):
        for v in range(1, 9):
            qty = TicketQuantity(value=v)
            assert qty.value == v

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            TicketQuantity(value=0)

    def test_nine_raises(self):
        with pytest.raises(ValueError):
            TicketQuantity(value=9)


class TestAttendeeInfo:
    def test_create_valid(self):
        info = AttendeeInfo(name="John Doe", email="john@example.com", phone="+34 123 456 789")
        assert info.name == "John Doe"
        assert info.email == "john@example.com"

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name is required"):
            AttendeeInfo(name="", email="john@example.com")

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError, match="Valid attendee email"):
            AttendeeInfo(name="John", email="invalid-email")

    def test_repr(self):
        info = AttendeeInfo(name="John", email="john@example.com")
        assert "John" in repr(info)