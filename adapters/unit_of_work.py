"""SQLAlchemy Unit of Work implementation."""
from contextlib import contextmanager
from typing import Generator, List, Optional
from uuid import UUID

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from adapters.orm import mapper_registry, OutboxEvent
from domain.models import Order, Payment, Plan
from domain.repositories import (
    OrderRepository, PaymentRepository, PlanRepository,
    OrderReadRepository, PlanReadRepository,
    PlanSearchQuery, PlanSummary, PlanDetail, OrderSummary, OrderStatusDetail
)
from domain.events import (
    OrderCreated, PaymentInitiated, PaymentConfirmed,
    PaymentFailed, OrderConfirmed, OrderCancelled
)


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, order: Order) -> None:
        self._session.add(order)

    def get(self, order_id: UUID) -> Optional[Order]:
        return self._session.get(Order, str(order_id))

    def get_by_payment_id(self, payment_id: UUID) -> Optional[Order]:
        return self._session.query(Order).filter_by(payment_id=str(payment_id)).first()


class SqlAlchemyPaymentRepository(PaymentRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, payment: Payment) -> None:
        self._session.add(payment)

    def get(self, payment_id: UUID) -> Optional[Payment]:
        return self._session.get(Payment, str(payment_id))

    def get_by_order_id(self, order_id: UUID) -> Optional[Payment]:
        return self._session.query(Payment).filter_by(order_id=str(order_id)).first()


class SqlAlchemyPlanRepository(PlanRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, plan: Plan) -> None:
        self._session.add(plan)

    def get(self, plan_id: UUID) -> Optional[Plan]:
        return self._session.get(Plan, str(plan_id))

    def get_by_tm_id(self, tm_plan_id: str) -> Optional[Plan]:
        return self._session.query(Plan).filter_by(tm_plan_id=tm_plan_id).first()


class SqlAlchemyOrderReadRepository(OrderReadRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_order_summary(self, order_id: UUID) -> Optional[OrderSummary]:
        order = self._session.get(Order, str(order_id))
        if not order:
            return None
        return OrderSummary(
            order_id=order.order_id,
            plan_id=order.plan_id,
            plan_name="",  # Would need join
            status=order.status,
            quantity=order.quantity.value,
            total_amount=float(order.total_amount.amount),
            currency=order.total_amount.currency.value,
            created_at=order.created_at.isoformat() if hasattr(order, 'created_at') else "",
        )

    def list_orders(self, customer_email: str, cursor: Optional[str], limit: int) -> List[OrderSummary]:
        # Simplified - would need join with attendees for email filtering
        query = self._session.query(Order)
        if cursor:
            query = query.filter(Order.order_id > cursor)
        return [OrderSummary(
            order_id=o.order_id,
            plan_id=o.plan_id,
            plan_name="",
            status=o.status,
            quantity=o.quantity.value,
            total_amount=float(o.total_amount.amount),
            currency=o.total_amount.currency.value,
            created_at=o.created_at.isoformat() if hasattr(o, 'created_at') else "",
        ) for o in query.limit(limit).all()]


class SqlAlchemyPlanReadRepository(PlanReadRepository):
    def __init__(self, session: Session):
        self._session = session

    def search_plans(self, query: PlanSearchQuery) -> List[PlanSummary]:
        q = self._session.query(Plan)
        if query.query:
            q = q.filter(Plan.name.ilike(f"%{query.query}%"))
        if query.date_from:
            q = q.filter(Plan.start_date >= query.date_from)
        if query.date_to:
            q = q.filter(Plan.start_date <= query.date_to)
        if query.cursor:
            q = q.filter(Plan.plan_id > query.cursor)
        plans = q.limit(query.limit).all()
        return [PlanSummary(
            plan_id=p.plan_id,
            tm_plan_id=p.tm_plan_id,
            name=p.name,
            url=p.url,
            image_url=p.image_url,
            start_date=p.date_range.start.isoformat(),
            start_time=p.date_range.start.strftime("%H:%M"),
            timezone=p.date_range.timezone,
            venue_name=p.venue_name,
            venue_city=p.venue_city,
            venue_state=p.venue_state,
            min_price=float(p.min_price.amount),
            max_price=float(p.max_price.amount),
            currency=p.min_price.currency.value,
        ) for p in plans]

    def get_plan(self, plan_id: UUID) -> Optional[PlanDetail]:
        plan = self._session.get(Plan, str(plan_id))
        if not plan:
            return None
        return PlanDetail(
            plan_id=plan.plan_id,
            tm_plan_id=plan.tm_plan_id,
            name=plan.name,
            url=plan.url,
            image_url=plan.image_url,
            date_range=plan.date_range,
            venue_name=plan.venue_name,
            venue_city=plan.venue_city,
            venue_state=plan.venue_state,
            min_price=float(plan.min_price.amount),
            max_price=float(plan.max_price.amount),
            currency=plan.min_price.currency.value,
            seat_map=[],  # TODO: load from plan
        )


class SqlAlchemyUnitOfWork:
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._session: Optional[Session] = None
        self._domain_events: List = []

        # Initialize mappers
        from adapters.orm import start_mappers
        start_mappers()

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
        for obj in self.session:
            if hasattr(obj, 'domain_events'):
                self._domain_events.extend(obj.domain_events)
                obj.clear_domain_events()

    def _write_outbox_events(self) -> None:
        """Write collected domain events to outbox table."""
        for event in self._domain_events:
            outbox_event = OutboxEvent(
                aggregate_id=event.aggregate_id if hasattr(event, 'aggregate_id') else None,
                aggregate_type=type(event).__name__,
                event_type=type(event).__name__,
                payload=self._serialize_event(event),
            )
            self.session.add(outbox_event)

    def _serialize_event(self, event) -> dict:
        """Serialize domain event to JSON-compatible dict."""
        data = {}
        for key, value in event.__dict__.items():
            if key.startswith('_'):
                continue
            if hasattr(value, 'isoformat'):  # datetime
                data[key] = value.isoformat()
            elif hasattr(value, '__dict__'):  # nested object
                data[key] = str(value)
            else:
                data[key] = value
        return data

    def commit(self) -> None:
        self._collect_domain_events()
        self._write_outbox_events()
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None