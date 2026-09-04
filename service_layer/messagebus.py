"""Message bus for command/query dispatching using singledispatch."""

from functools import singledispatch
from typing import Any

from service_layer.commands import (
    CancelOrderCommand,
    ConfirmPaymentCommand,
    CreateOrderCommand,
    RefundOrderCommand,
    ReserveSeatsCommand,
    SyncPlansCommand,
)
from service_layer.queries import GetOrderQuery, GetPlanQuery, ListOrdersQuery, SearchPlansQuery


class MessageBus:
    """Dispatches commands and queries to appropriate handlers using singledispatch."""

    def __init__(self, order_handler, plan_handler, query_handler):
        self._order_handler = order_handler
        self._plan_handler = plan_handler
        self._query_handler = query_handler

    def handle_command(self, command) -> Any:
        """Handle a command (write operation) using singledispatch."""
        return self._handle_command(command)

    def handle_query(self, query) -> Any:
        """Handle a query (read operation) using singledispatch."""
        return self._handle_query(query)

    # Public health check methods
    def check_database(self) -> bool:
        """Check database connectivity."""
        try:
            from sqlalchemy import text

            uow = self._order_handler._uow
            with uow:
                uow.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def check_redis(self) -> bool:
        """Check Redis connectivity."""
        try:
            tm_adapter = self._order_handler._tm
            if tm_adapter.redis:
                tm_adapter.redis.ping()
                return True
            return False
        except Exception:
            return False

    def check_ticketmaster(self) -> bool:
        """Check Ticketmaster OAuth token."""
        try:
            tm_adapter = self._order_handler._tm
            token = tm_adapter._get_access_token()
            return token is not None
        except Exception:
            return False

    def flush_outbox(self) -> None:
        """Flush outbox events."""
        uow = self._order_handler._uow
        uow.flush_outbox()

    def shutdown(self) -> None:
        """Graceful shutdown: flush outbox, dispose engine, close Redis."""
        # Flush outbox
        try:
            self.flush_outbox()
        except Exception:
            pass

        # Dispose engine
        try:
            uow = self._order_handler._uow
            uow._engine.dispose()
        except Exception:
            pass

        # Close Redis
        try:
            tm_adapter = self._order_handler._tm
            if tm_adapter.redis:
                tm_adapter.redis.close()
        except Exception:
            pass

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
