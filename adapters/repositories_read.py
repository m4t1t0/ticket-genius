"""Read repository implementations."""

from uuid import UUID

from sqlalchemy.orm import Session

from adapters.orm import Order, Plan
from domain.repositories import (
    OrderReadRepository,
    OrderSummary,
    PlanDetail,
    PlanReadRepository,
    PlanSearchQuery,
    PlanSummary,
)
from service_layer.cursor import apply_cursor_filter


class SqlAlchemyOrderReadRepository(OrderReadRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_order_summary(self, order_id: UUID) -> OrderSummary | None:
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
            created_at=order.created_at.isoformat() if hasattr(order, "created_at") else "",
        )

    def list_orders(
        self, customer_email: str, cursor: str | None, limit: int
    ) -> list[OrderSummary]:
        query = self._session.query(Order).order_by(Order.created_at.desc(), Order.order_id.desc())

        # Apply cursor-based pagination
        query, _ = apply_cursor_filter(query, cursor, Order.order_id, Order.created_at)

        return [
            OrderSummary(
                order_id=o.order_id,
                plan_id=o.plan_id,
                plan_name="",
                status=o.status,
                quantity=o.quantity.value,
                total_amount=float(o.total_amount.amount),
                currency=o.total_amount.currency.value,
                created_at=o.created_at.isoformat() if hasattr(o, "created_at") else "",
            )
            for o in query.limit(limit).all()
        ]


class SqlAlchemyPlanReadRepository(PlanReadRepository):
    def __init__(self, session: Session):
        self._session = session

    def search_plans(self, query: PlanSearchQuery) -> list[PlanSummary]:
        # This method is kept for backward compatibility but delegates to TM adapter
        # The actual search is now done via TicketmasterAdapter in QueryHandler
        # This fallback is for local-only queries
        q = self._session.query(Plan).order_by(Plan.start_date.desc(), Plan.plan_id.desc())
        if query.query:
            q = q.filter(Plan.name.ilike(f"%{query.query}%"))
        if query.date_from:
            q = q.filter(Plan.start_date >= query.date_from)
        if query.date_to:
            q = q.filter(Plan.start_date <= query.date_to)

        # Apply cursor-based pagination
        q, _ = apply_cursor_filter(q, query.cursor, Plan.plan_id, Plan.start_date)

        plans = q.limit(query.limit).all()
        return [
            PlanSummary(
                plan_id=p.plan_id,
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
            )
            for p in plans
        ]

    def get_plan(self, plan_id: UUID) -> PlanDetail | None:
        plan = self._session.get(Plan, str(plan_id))
        if not plan:
            return None
        return PlanDetail(
            plan_id=plan.plan_id,
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
