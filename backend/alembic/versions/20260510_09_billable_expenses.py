"""#263 P2: billable_expenses table

Revision ID: 20260510_09
Revises: 20260510_08
Create Date: 2026-05-10 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_09"
down_revision = "20260510_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billable_expenses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("bill_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("markup_pct", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("invoice_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billable_expenses_customer_id", "billable_expenses", ["customer_id"])
    op.create_index("ix_billable_expenses_status", "billable_expenses", ["status"])


def downgrade() -> None:
    op.drop_index("ix_billable_expenses_status", table_name="billable_expenses")
    op.drop_index("ix_billable_expenses_customer_id", table_name="billable_expenses")
    op.drop_table("billable_expenses")
