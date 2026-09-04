from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency = Currency.EUR

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Money amount cannot have more than 2 decimal places")

    def __composite_values__(self):
        return (self.amount, self.currency)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Cannot add Money with different currencies")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Cannot subtract Money with different currencies")
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: int) -> "Money":
        return Money(self.amount * factor, self.currency)

    def __repr__(self) -> str:
        return f"Money({self.amount:.2f} {self.currency.value})"


@dataclass(frozen=True)
class SeatId:
    """Immutable seat identifier in format 'section-row-number'."""

    section: str
    row: str
    number: str

    def __post_init__(self):
        if not self.section or not self.row or not self.number:
            raise ValueError("SeatId section, row, and number are required")

    def __str__(self) -> str:
        return f"{self.section}-{self.row}-{self.number}"

    @classmethod
    def from_string(cls, s: str) -> "SeatId":
        """Parse SeatId from string format 'section-row-number'."""
        parts = s.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid SeatId format: {s}. Expected 'section-row-number'")
        return cls(section=parts[0], row=parts[1], number=parts[2])

    def __composite_values__(self):
        return (self.section, self.row, self.number)

    def __repr__(self) -> str:
        return f"SeatId(section={self.section}, row={self.row}, number={self.number})"


@dataclass
class Seat:
    """Mutable seat entity with a SeatId."""

    seat_id: SeatId

    def __post_init__(self):
        if not isinstance(self.seat_id, SeatId):
            raise ValueError("Seat must have a SeatId")

    @property
    def section(self) -> str:
        return self.seat_id.section

    @property
    def row(self) -> str:
        return self.seat_id.row

    @property
    def number(self) -> str:
        return self.seat_id.number

    @classmethod
    def from_string(cls, s: str) -> "Seat":
        """Create Seat from string format 'section-row-number'."""
        return cls(seat_id=SeatId.from_string(s))

    @classmethod
    def from_parts(cls, section: str, row: str, number: str) -> "Seat":
        """Create Seat from parts."""
        return cls(seat_id=SeatId(section=section, row=row, number=number))

    def __repr__(self) -> str:
        return f"Seat(seat_id={self.seat_id})"


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime
    timezone: str

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("DateRange start must be before end")
        if not self.timezone:
            raise ValueError("DateRange timezone is required")

    def __composite_values__(self):
        return (self.start, self.end, self.timezone)

    def __repr__(self) -> str:
        return f"DateRange(start={self.start.isoformat()}, end={self.end.isoformat()}, tz={self.timezone})"


@dataclass(frozen=True)
class TicketQuantity:
    value: int

    def __post_init__(self):
        if not 1 <= self.value <= 8:
            raise ValueError("TicketQuantity must be between 1 and 8")

    def __repr__(self) -> str:
        return f"TicketQuantity({self.value})"


@dataclass
class AttendeeInfo:
    name: str
    email: str
    phone: str | None = None

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Attendee name is required")
        if not self.email or "@" not in self.email:
            raise ValueError("Valid attendee email is required")

    def __composite_values__(self):
        return (self.name, self.email, self.phone)

    def __repr__(self) -> str:
        return f"AttendeeInfo(name={self.name}, email={self.email}, phone={self.phone})"
