"""Initial migration: orders, payments, plans, attendees, seats, outbox

Revision ID: 6e20502a83a3
Revises:
Create Date: 2026-09-01 15:48:18.885456

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e20502a83a3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Plans table
    op.create_table(
        "plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tm_plan_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("image_url", sa.String(1000), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False),
        sa.Column("venue_name", sa.String(255), nullable=False),
        sa.Column("venue_city", sa.String(100), nullable=False),
        sa.Column("venue_state", sa.String(100), nullable=False),
        sa.Column("min_price_cents", sa.Integer(), nullable=False),
        sa.Column("max_price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, default="EUR"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tm_last_modified", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_plans_tm_plan_id", "plans", ["tm_plan_id"], unique=True)
    op.create_index("ix_plans_date_range", "plans", ["start_date", "end_date"])
    op.create_index("ix_plans_venue_city", "plans", ["venue_city"])

    # Orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_id", sa.String(36), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("quantity_value", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, default="EUR"),
        sa.Column("status", sa.String(30), nullable=False, default="PENDING"),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_orders_plan_id", "orders", ["plan_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_payment_id", "orders", ["payment_id"])

    # Payments table
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, default="EUR"),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, default="CREATED"),
        sa.Column("provider_ref", sa.String(255), nullable=True),
        sa.Column("intent_id", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=True)
    op.create_index("ix_payments_status", "payments", ["status"])

    # Attendees table
    op.create_table(
        "attendees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
    )
    op.create_index("ix_attendees_order_id", "attendees", ["order_id"])

    # Seats table
    op.create_table(
        "seats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("row", sa.String(50), nullable=False),
        sa.Column("number", sa.String(50), nullable=False),
    )
    op.create_index("ix_seats_order_id", "seats", ["order_id"])

    # Outbox table
    op.create_table(
        "outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
    )
    op.create_index(
        "ix_outbox_unprocessed",
        "outbox",
        ["processed_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index("ix_outbox_aggregate", "outbox", ["aggregate_id", "aggregate_type"])


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("seats")
    op.drop_table("attendees")
    op.drop_table("payments")
    op.drop_table("orders")
    op.drop_table("plans")
