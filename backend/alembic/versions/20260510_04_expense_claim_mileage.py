"""#324 P2: mileage tracking on expense_claim_lines

Revision ID: 20260510_04
Revises: 20260510_03
Create Date: 2026-05-10 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_04"
down_revision = "20260510_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("expense_claim_lines") as batch:
        batch.add_column(sa.Column("line_kind", sa.String(length=20), nullable=False, server_default="expense"))
        batch.add_column(sa.Column("miles", sa.Numeric(10, 2), nullable=True))
        batch.add_column(sa.Column("mileage_rate_used", sa.Numeric(8, 4), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("expense_claim_lines") as batch:
        batch.drop_column("mileage_rate_used")
        batch.drop_column("miles")
        batch.drop_column("line_kind")
