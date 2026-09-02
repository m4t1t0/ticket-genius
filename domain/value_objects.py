from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: Currency = Currency.EUR

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Money amount cannot have more than 2 decimal places")

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


@dataclass(frozen=True, slots=True)
class Seat:
    section: str
    row: str
    number: str

    def __post_init__(self):
        if not self.section or not self.row or not self.number:
            raise ValueError("Seat section, row, and number are required")

    def __repr__(self) -> str:
        return f"Seat(section={self.section}, row={self.row}, number={self.number})"


@dataclass(frozen=True, slots=True)
class DateRange:
    start: datetime
    end: datetime
    timezone: str

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("DateRange start must be before end")
        if not self.timezone:
            raise ValueError("DateRange timezone is required")

    def __repr__(self) -> str:
        return f"DateRange(start={self.start.isoformat()}, end={self.end.isoformat()}, tz={self.timezone})"


@dataclass(frozen=True, slots=True)
class TicketQuantity:
    value: int

    def __post_init__(self):
        if not 1 <= self.value <= 8:
            raise ValueError("TicketQuantity must be between 1 and 8")

    def __repr__(self) -> str:
        return f"TicketQuantity({self.value})"


@dataclass(frozen=True, slots=True)
class AttendeeInfo:
    name: str
    email: str
    phone: Optional[str] = None

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Attendee name is required")
        if not self.email or "@" not in self.email:
            raise ValueError("Valid attendee email is required")

    def __repr__(self) -> str:
        return f"AttendeeInfo(name={self.name}, email={self.email})"