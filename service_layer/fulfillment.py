"""Order fulfillment service - handles TM purchase flow after payment confirmation."""

from typing import Optional, List
from uuid import UUID

from adapters.ticketmaster import TicketmasterAdapter
from domain.models import Order, Plan
from domain.value_objects import Seat
from domain.exceptions import PlanNotFoundError
from domain.events import OrderConfirmed

from service_layer.seat_holds import release_seat_holds


class FulfillOrderService:
    """
    Handles the Ticketmaster purchase flow after payment is confirmed.
    
    This separates the fulfillment concern from payment confirmation,
    following the Single Responsibility Principle.
    """

    def __init__(
        self,
        tm_adapter: TicketmasterAdapter,
    ):
        self._tm = tm_adapter

    def fulfill(
        self,
        order: Order,
        plan: Plan,
    ) -> List[dict]:
        """
        Execute the TM purchase flow:
        1. Create TM offer with idempotency key
        2. Accept TM offer with idempotency key
        3. Return fulfillment details (tickets)
        
        Args:
            order: The confirmed order
            plan: The plan for the event
            
        Returns:
            List of ticket dicts from TM fulfillment
        """
        # Create TM offer with idempotency key
        idempotency_key = f"order_{order.order_id}"
        tm_order = self._tm.create_order(
            plan_id=plan.tm_plan_id,
            quantity=order.quantity.value,
            seat_ids=[f"{s.section}-{s.row}-{s.number}" for s in order.seats],
            idempotency_key=idempotency_key,
        )

        # Accept TM offer with idempotency key
        accept_idempotency_key = f"accept_{order.order_id}"
        seat_ids = [f"{s.section}-{s.row}-{s.number}" for s in order.seats]
        acceptance = self._tm.accept_offer(
            tm_order["offer_id"],
            idempotency_key=accept_idempotency_key,
            seat_ids=seat_ids,
        )

        # Extract tickets from fulfillment
        tickets = acceptance.get("fulfillment", {}).get("tickets", [])

        # Release seat holds after successful fulfillment
        _release_seat_holds(self._tm.redis, order.plan_id, seat_ids, order.order_id)

        # Add domain event for fulfillment
        order.add_domain_event(
            OrderConfirmed(
                order_id=order.order_id,
                tickets=tickets,
            )
        )

        return tickets