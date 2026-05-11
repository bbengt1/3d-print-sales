"""#324 P2: expense claim bill_id (reimburse-as-Bill linkage)

Revision ID: 20260511_05
Revises: 20260511_04
Create Date: 2026-05-11 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260511_05"
down_revision = "20260511_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("expense_claims") as batch:
        batch.add_column(sa.Column("bill_id", sa.UUID(), nullable=True))
        batch.create_foreign_key(
            "fk_expense_claims_bill", "bills", ["bill_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("expense_claims") as batch:
        batch.drop_constraint("fk_expense_claims_bill", type_="foreignkey")
        batch.drop_column("bill_id")
