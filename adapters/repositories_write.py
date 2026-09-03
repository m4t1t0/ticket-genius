"""Write repository implementations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from adapters.orm import Order, Payment, Plan
from domain.repositories import (
    OrderRepository, PaymentRepository, PlanRepository,
)
from domain.exceptions import OptimisticLockError


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, order: Order) -> None:
        self._session.add(order)

    def get(self, order_id: UUID) -> Optional[Order]:
        return self._session.get(Order, str(order_id))

    def get_by_payment_id(self, payment_id: UUID) -> Optional[Order]:
        return self._session.query(Order).filter_by(payment_id=str(payment_id)).first()

    def update(self, order: Order) -> None:
        """Update order with optimistic locking."""
        from sqlalchemy import update, text
        stmt = (
            update(Order.__table__)
            .where(Order.order_id == str(order.order_id))
            .where(Order.version == order.version)
            .values(
                status=order.status,
                payment_id=str(order.payment_id) if order.payment_id else None,
                version=order.version + 1,
                updated_at=text("NOW()"),
            )
        )
        result = self._session.execute(stmt)
        if result.rowcount == 0:
            raise OptimisticLockError("Order", str(order.order_id))
        order.version += 1


class SqlAlchemyPaymentRepository(PaymentRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, payment: Payment) -> None:
        self._session.add(payment)

    def get(self, payment_id: UUID) -> Optional[Payment]:
        return self._session.get(Payment, str(payment_id))

    def get_by_order_id(self, order_id: UUID) -> Optional[Payment]:
        return self._session.query(Payment).filter_by(order_id=str(order_id)).first()

    def update(self, payment: Payment) -> None:
        """Update payment with optimistic locking."""
        from sqlalchemy import update, text
        stmt = (
            update(Payment.__table__)
            .where(Payment.payment_id == str(payment.payment_id))
            .where(Payment.version == payment.version)
            .values(
                status=payment.status,
                provider_ref=payment.provider_ref,
                version=payment.version + 1,
                updated_at=text("NOW()"),
            )
        )
        result = self._session.execute(stmt)
        if result.rowcount == 0:
            raise OptimisticLockError("Payment", str(payment.payment_id))
        payment.version += 1


class SqlAlchemyPlanRepository(PlanRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, plan: Plan) -> None:
        self._session.add(plan)

    def get(self, plan_id: UUID) -> Optional[Plan]:
        return self._session.get(Plan, str(plan_id))

    def get_by_tm_id(self, tm_plan_id: str) -> Optional[Plan]:
        return self._session.query(Plan).filter_by(_tm_plan_id=tm_plan_id).first()

    def update(self, plan: Plan) -> None:
        """Update plan with optimistic locking."""
        from sqlalchemy import update, text
        stmt = (
            update(Plan.__table__)
            .where(Plan.plan_id == str(plan.plan_id))
            .where(Plan.version == plan.version)
            .values(
                name=plan.name,
                url=plan.url,
                image_url=plan.image_url,
                venue_name=plan.venue_name,
                venue_city=plan.venue_city,
                venue_state=plan.venue_state,
                min_price_cents=int(plan.min_price.amount * 100),
                max_price_cents=int(plan.max_price.amount * 100),
                currency=plan.min_price.currency,
                seat_prices_json=plan.seat_prices_json,
                last_synced_at=plan.last_synced_at,
                tm_last_modified=plan.tm_last_modified,
                version=plan.version + 1,
                updated_at=text("NOW()"),
            )
        )
        result = self._session.execute(stmt)
        if result.rowcount == 0:
            raise OptimisticLockError("Plan", str(plan.plan_id))
        plan.version += 1