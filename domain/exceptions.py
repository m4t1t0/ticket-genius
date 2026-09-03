"""Domain exceptions with error codes for RFC 7807 Problem Details."""

from typing import Optional, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    """Standard error codes for the domain."""
    # Plan errors
    PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
    PLAN_STALE = "PLAN_STALE"
    PLAN_INACTIVE = "PLAN_INACTIVE"

    # Order errors
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    ORDER_INVALID_STATUS = "ORDER_INVALID_STATUS"
    ORDER_INSUFFICIENT_INVENTORY = "ORDER_INSUFFICIENT_INVENTORY"
    ORDER_SEAT_MISMATCH = "ORDER_SEAT_MISMATCH"

    # Payment errors
    PAYMENT_NOT_FOUND = "PAYMENT_NOT_FOUND"
    PAYMENT_DECLINED = "PAYMENT_DECLINED"
    PAYMENT_INVALID_STATUS = "PAYMENT_INVALID_STATUS"
    PAYMENT_INTENT_EXPIRED = "PAYMENT_INTENT_EXPIRED"
    IDEMPOTENCY_KEY_USED = "IDEMPOTENCY_KEY_USED"

    # Provider errors
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_AUTHENTICATION_FAILED = "PROVIDER_AUTHENTICATION_FAILED"

    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"


class DomainException(Exception):
    """Base domain exception with error code."""

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.VALIDATION_ERROR,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class PlanNotFoundError(DomainException):
    """Plan not found."""

    def __init__(self, plan_id: str, details: Optional[dict] = None):
        super().__init__(
            f"Plan {plan_id} not found",
            code=ErrorCode.PLAN_NOT_FOUND,
            details=details,
        )


class PlanStaleError(DomainException):
    """Plan data is stale and needs refresh."""

    def __init__(self, plan_id: str, details: Optional[dict] = None):
        super().__init__(
            f"Plan {plan_id} data is stale",
            code=ErrorCode.PLAN_STALE,
            details=details,
        )


class OrderNotFoundError(DomainException):
    """Order not found."""

    def __init__(self, order_id: str, details: Optional[dict] = None):
        super().__init__(
            f"Order {order_id} not found",
            code=ErrorCode.ORDER_NOT_FOUND,
            details=details,
        )


class OrderInvalidStatusError(DomainException):
    """Order is in invalid state for operation."""

    def __init__(self, order_id: str, current_status: str, expected_status: str, details: Optional[dict] = None):
        super().__init__(
            f"Order {order_id} is in status {current_status}, expected {expected_status}",
            code=ErrorCode.ORDER_INVALID_STATUS,
            details=details or {"current_status": current_status, "expected_status": expected_status},
        )


class InsufficientInventoryError(DomainException):
    """Not enough inventory/seats available."""

    def __init__(self, plan_id: str, requested: int, available: int, details: Optional[dict] = None):
        super().__init__(
            f"Insufficient inventory for plan {plan_id}: requested {requested}, available {available}",
            code=ErrorCode.ORDER_INSUFFICIENT_INVENTORY,
            details=details or {"plan_id": plan_id, "requested": requested, "available": available},
        )


class SeatMismatchError(DomainException):
    """Seat selection doesn't match quantity."""

    def __init__(self, expected: int, got: int, details: Optional[dict] = None):
        super().__init__(
            f"Seat mismatch: expected {expected} seats, got {got}",
            code=ErrorCode.ORDER_SEAT_MISMATCH,
            details=details or {"expected": expected, "got": got},
        )


class PaymentNotFoundError(DomainException):
    """Payment not found."""

    def __init__(self, payment_id: str, details: Optional[dict] = None):
        super().__init__(
            f"Payment {payment_id} not found",
            code=ErrorCode.PAYMENT_NOT_FOUND,
            details=details,
        )


class PaymentDeclinedError(DomainException):
    """Payment was declined by provider."""

    def __init__(self, payment_id: str, reason: str, details: Optional[dict] = None):
        super().__init__(
            f"Payment {payment_id} declined: {reason}",
            code=ErrorCode.PAYMENT_DECLINED,
            details=details or {"payment_id": payment_id, "reason": reason},
        )


class PaymentInvalidStatusError(DomainException):
    """Payment is in invalid state for operation."""

    def __init__(self, payment_id: str, current_status: str, expected_status: str, details: Optional[dict] = None):
        super().__init__(
            f"Payment {payment_id} is in status {current_status}, expected {expected_status}",
            code=ErrorCode.PAYMENT_INVALID_STATUS,
            details=details or {"current_status": current_status, "expected_status": expected_status},
        )


class IdempotencyKeyUsedError(DomainException):
    """Idempotency key already used."""

    def __init__(self, key: str, details: Optional[dict] = None):
        super().__init__(
            f"Idempotency key {key} already used",
            code=ErrorCode.IDEMPOTENCY_KEY_USED,
            details=details or {"key": key},
        )


class ProviderError(DomainException):
    """External provider error."""

    def __init__(self, provider: str, message: str, details: Optional[dict] = None):
        super().__init__(
            f"Provider {provider} error: {message}",
            code=ErrorCode.PROVIDER_ERROR,
            details=details or {"provider": provider, "message": message},
        )


class ProviderUnavailableError(DomainException):
    """External provider is unavailable."""

    def __init__(self, provider: str, details: Optional[dict] = None):
        super().__init__(
            f"Provider {provider} is unavailable",
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            details=details or {"provider": provider},
        )


class ProviderRateLimitedError(DomainException):
    """External provider rate limited."""

    def __init__(self, provider: str, retry_after: Optional[int] = None, details: Optional[dict] = None):
        super().__init__(
            f"Provider {provider} rate limited",
            code=ErrorCode.PROVIDER_RATE_LIMITED,
            details=details or {"provider": provider, "retry_after": retry_after},
        )


class ProviderAuthenticationError(DomainException):
    """Provider authentication failed."""

    def __init__(self, provider: str, details: Optional[dict] = None):
        super().__init__(
            f"Provider {provider} authentication failed",
            code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
            details=details or {"provider": provider},
        )


class ValidationError(DomainException):
    """Input validation error."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(
            message,
            code=ErrorCode.VALIDATION_ERROR,
            details=details or {"field": field} if field else details,
        )


class OptimisticLockError(DomainException):
    """Optimistic locking conflict - entity was modified by another transaction."""

    def __init__(self, entity_type: str, entity_id: str, details: Optional[dict] = None):
        super().__init__(
            f"{entity_type} {entity_id} was modified by another transaction",
            code="OPTIMISTIC_LOCK_ERROR",
            details=details or {"entity_type": entity_type, "entity_id": entity_id},
        )