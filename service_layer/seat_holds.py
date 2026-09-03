"""Seat hold utilities for Redis-based seat reservation."""

from typing import List
from uuid import UUID


# Seat hold constants
SEAT_HOLD_TTL = 600  # 10 minutes in seconds
SEAT_HOLD_PREFIX = "SEAT_HOLD"

# Payment confirmation idempotency constants
PAYMENT_CONFIRM_TTL = 86400  # 24 hours in seconds
PAYMENT_CONFIRM_PREFIX = "payment_confirm"


def acquire_seat_holds(redis, plan_id: UUID, seat_ids: List[str], order_id: UUID) -> bool:
    """
    Acquire seat holds in Redis using SETNX with TTL.
    Returns True if all seats acquired, False if any seat already held.
    """
    if not redis:
        return True  # No Redis, skip hold (for testing)
    
    acquired = []
    for seat_id in seat_ids:
        key = f"{SEAT_HOLD_PREFIX}:{plan_id}:{seat_id}"
        # Use SET NX EX for atomic acquire with TTL
        result = redis.set(key, str(order_id), nx=True, ex=SEAT_HOLD_TTL)
        if result:
            acquired.append(seat_id)
        else:
            # Failed to acquire, release any already acquired
            for acquired_seat in acquired:
                release_key = f"{SEAT_HOLD_PREFIX}:{plan_id}:{acquired_seat}"
                redis.delete(release_key)
            return False
    return True


def release_seat_holds(redis, plan_id: UUID, seat_ids: List[str], order_id: UUID) -> None:
    """Release seat holds for the given order."""
    if not redis:
        return
    for seat_id in seat_ids:
        key = f"{SEAT_HOLD_PREFIX}:{plan_id}:{seat_id}"
        # Only delete if the value matches our order_id (prevent releasing others' holds)
        current = redis.get(key)
        if current == str(order_id):
            redis.delete(key)


def check_payment_idempotency(redis, payment_id: UUID, idempotency_key: str) -> bool:
    """
    Check and set payment confirmation idempotency key.
    Returns True if this is the first attempt, False if already processed.
    """
    if not redis:
        return True
    key = f"{PAYMENT_CONFIRM_PREFIX}:{payment_id}:{idempotency_key}"
    result = redis.set(key, "1", nx=True, ex=PAYMENT_CONFIRM_TTL)
    return result is True