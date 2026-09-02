"""Message bus for command/query dispatching."""
from typing import Callable, Dict, Any, TypeVar
from functools import singledispatch

from service_layer.commands import (
    CreateOrderCommand, ConfirmPaymentCommand, CancelOrderCommand,
    RefundOrderCommand, SyncPlansCommand, ReserveSeatsCommand
)
from service_layer.queries import (
    SearchPlansQuery, GetOrderQuery, ListOrdersQuery, GetPlanQuery
)
from service_layer.handlers import OrderCommandHandler, PlanCommandHandler, QueryHandler


class MessageBus:
    """Dispatches commands and queries to appropriate handlers."""

    def __init__(
        self,
        order_handler: OrderCommandHandler,
        plan_handler: PlanCommandHandler,
        query_handler: QueryHandler,
    ):
        self._order_handler = order_handler
        self._plan_handler = plan_handler
        self._query_handler = query_handler

    def handle_command(self, command):
        """Handle a command (write operation)."""
        if isinstance(command, CreateOrderCommand):
            return self._order_handler.handle_create_order(command)
        elif isinstance(command, ConfirmPaymentCommand):
            return self._order_handler.handle_confirm_payment(command)
        elif isinstance(command, CancelOrderCommand):
            return self._order_handler.handle_cancel_order(command)
        elif isinstance(command, RefundOrderCommand):
            return self._order_handler.handle_refund_order(command)
        elif isinstance(command, SyncPlansCommand):
            return self._plan_handler.handle_sync_plans(command)
        else:
            raise ValueError(f"Unknown command: {type(command)}")

    def handle_query(self, query):
        """Handle a query (read operation)."""
        if isinstance(query, SearchPlansQuery):
            return self._query_handler.handle_search_plans(query)
        elif isinstance(query, GetPlanQuery):
            return self._query_handler.handle_get_plan(query)
        elif isinstance(query, GetOrderQuery):
            return self._query_handler.handle_get_order(query)
        elif isinstance(query, ListOrdersQuery):
            return self._query_handler.handle_list_orders(query)
        else:
            raise ValueError(f"Unknown query: {type(query)}")