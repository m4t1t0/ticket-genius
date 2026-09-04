"""SQLAlchemy Unit of Work implementation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from adapters.orm import OutboxEvent
from adapters.repositories_read import SqlAlchemyOrderReadRepository, SqlAlchemyPlanReadRepository

# Import separated repository implementations
from adapters.repositories_write import (
    SqlAlchemyOrderRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyPlanRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._session: Session | None = None
        self._domain_events: list = []

    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = self._session_factory()
        return self._session

    @property
    def orders(self) -> SqlAlchemyOrderRepository:
        return SqlAlchemyOrderRepository(self.session)

    @property
    def payments(self) -> SqlAlchemyPaymentRepository:
        return SqlAlchemyPaymentRepository(self.session)

    @property
    def plans(self) -> SqlAlchemyPlanRepository:
        return SqlAlchemyPlanRepository(self.session)

    @property
    def orders_read(self) -> SqlAlchemyOrderReadRepository:
        return SqlAlchemyOrderReadRepository(self.session)

    @property
    def plans_read(self) -> SqlAlchemyPlanReadRepository:
        return SqlAlchemyPlanReadRepository(self.session)

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self._collect_domain_events()
            self._write_outbox_events()
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()

    def _collect_domain_events(self) -> None:
        """Collect domain events from all loaded aggregates."""
        # Only check new and dirty objects, not the entire session
        for obj in self.session.new:
            if hasattr(obj, "domain_events"):
                self._domain_events.extend(obj.domain_events)
                obj.clear_domain_events()
        for obj in self.session.dirty:
            if hasattr(obj, "domain_events"):
                self._domain_events.extend(obj.domain_events)
                obj.clear_domain_events()

    def _write_outbox_events(self) -> None:
        """Write collected domain events to outbox table."""
        for event in self._domain_events:
            outbox_event = OutboxEvent(
                aggregate_id=event.aggregate_id if hasattr(event, "aggregate_id") else None,
                aggregate_type=type(event).__name__,
                event_type=type(event).__name__,
                payload=self._serialize_event(event),
            )
            self.session.add(outbox_event)

    def _serialize_event(self, event) -> dict:
        """Serialize domain event to JSON-compatible dict."""
        data = {}
        for key, value in event.__dict__.items():
            if key.startswith("_"):
                continue
            if hasattr(value, "isoformat"):  # datetime
                data[key] = value.isoformat()
            elif hasattr(value, "__dict__"):  # nested object
                data[key] = str(value)
            else:
                data[key] = value
        return data

    def commit(self) -> None:
        self._collect_domain_events()
        self._write_outbox_events()
        self.session.commit()

    def flush_outbox(self) -> None:
        """Public method to flush outbox events without committing transaction.
        Used during graceful shutdown to ensure pending events are persisted."""
        self._collect_domain_events()
        self._write_outbox_events()
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
