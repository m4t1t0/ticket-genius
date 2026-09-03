"""Message bus for command/query dispatching using singledispatch."""

from functools import singledispatch
from typing import Any, Union

from service_layer.commands import (
    CreateOrderCommand, ConfirmPaymentCommand, CancelOrderCommand,
    RefundOrderCommand, SyncPlansCommand, ReserveSeatsCommand,
)
from service_layer.queries import (
    SearchPlansQuery, GetOrderQuery, ListOrdersQuery, GetPlanQuery,
)


class MessageBus:
    """Dispatches commands and queries to appropriate handlers using singledispatch."""

    def __init__(
        self,
        order_handler,
        plan_handler,
        query_handler,
    ):
        self._order_handler = order_handler
        self._plan_handler = plan_handler
        self._query_handler = query_handler

    def handle_command(self, command) -> Any:
        """Handle a command (write operation) using singledispatch."""
        return self._handle_command(command)

    def handle_query(self, query) -> Any:
        """Handle a query (read operation) using singledispatch."""
        return self._handle_query(query)

    # Command handlers using singledispatch
    @singledispatch
    def _handle_command(self, command) -> Any:
        raise ValueError(f"Unknown command: {type(command).__name__}")

    @_handle_command.register
    def _(self, command: CreateOrderCommand):
        return self._order_handler.handle_create_order(command)

    @_handle_command.register
    def _(self, command: ConfirmPaymentCommand):
        return self._order_handler.handle_confirm_payment(command)

    @_handle_command.register
    def _(self, command: CancelOrderCommand):
        return self._order_handler.handle_cancel_order(command)

    @_handle_command.register
    def _(self, command: RefundOrderCommand):
        return self._order_handler.handle_refund_order(command)

    @_handle_command.register
    def _(self, command: SyncPlansCommand):
        return self._plan_handler.handle_sync_plans(command)

    @_handle_command.register
    def _(self, command: ReserveSeatsCommand):
        return self._order_handler.handle_reserve_seats(command)

    # Query handlers using singledispatch
    @singledispatch
    def _handle_query(self, query) -> Any:
        raise ValueError(f"Unknown query: {type(query).__name__}")

    @_handle_query.register
    def _(self, query: SearchPlansQuery):
        return self._query_handler.handle_search_plans(query)

    @_handle_query.register
    def _(self, query: GetPlanQuery):
        return self._query_handler.handle_get_plan(query)

    @_handle_query.register
    def _(self, query: GetOrderQuery):
        return self._query_handler.handle_get_order(query)

    @_handle_query.register
    def _(self, query: ListOrdersQuery):
        return self._query_handler.handle_list_orders(query)