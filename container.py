"""Dependency Injection container using python-dependency-injector."""

from dependency_injector import containers, providers

from config import get_settings
from adapters import (
    SqlAlchemyUnitOfWork,
    TicketmasterAdapter,
    PaymentSimulatorAdapter,
    get_redis_client,
)
from service_layer import (
    OrderCommandHandler,
    PlanCommandHandler,
    QueryHandler,
    MessageBus,
    FulfillOrderService,
)


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    # Configuration
    config = providers.Configuration()

    # Settings (singleton)
    settings = providers.Singleton(get_settings)

    # Infrastructure
    redis_client = providers.Factory(
        get_redis_client,
    )

    # Database
    unit_of_work = providers.Factory(
        SqlAlchemyUnitOfWork,
        database_url=settings.provided.database.url,
    )

    # External adapters
    ticketmaster_adapter = providers.Factory(
        TicketmasterAdapter,
        client_id=settings.provided.ticketmaster.client_id,
        client_secret=settings.provided.ticketmaster.client_secret,
        redis_client=redis_client,
        sandbox=settings.provided.ticketmaster.sandbox,
    )

    payment_adapter = providers.Factory(
        PaymentSimulatorAdapter,
    )

    # Service layer handlers
    fulfillment_service = providers.Factory(
        FulfillOrderService,
        tm_adapter=ticketmaster_adapter,
    )

    order_command_handler = providers.Factory(
        OrderCommandHandler,
        uow=unit_of_work,
        fulfillment_service=fulfillment_service,
        payment_adapter=payment_adapter,
    )

    plan_command_handler = providers.Factory(
        PlanCommandHandler,
        uow=unit_of_work,
        tm_adapter=ticketmaster_adapter,
    )

    query_handler = providers.Factory(
        QueryHandler,
        uow=unit_of_work,
        search_port=ticketmaster_adapter,
    )

    # Message bus
    message_bus = providers.Factory(
        MessageBus,
        order_handler=order_command_handler,
        plan_handler=plan_command_handler,
        query_handler=query_handler,
    )


def create_container() -> Container:
    """Create and configure the DI container."""
    container = Container()
    container.config.from_pydantic(get_settings())
    return container


# Global container instance (for convenience)
container = create_container()