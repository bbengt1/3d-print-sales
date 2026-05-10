"""#263 P2: late-payment-fee per-customer override columns

Revision ID: 20260510_07
Revises: 20260510_06
Create Date: 2026-05-10 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_07"
down_revision = "20260510_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("late_payment_fee_rate_pct", sa.Numeric(6, 3), nullable=True))
        batch.add_column(sa.Column("late_payment_fee_grace_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("customers") as batch:
        batch.drop_column("late_payment_fee_grace_days")
        batch.drop_column("late_payment_fee_rate_pct")
