"""add recurring expenses

Revision ID: 20260322_04
Revises: 20260322_03
Create Date: 2026-03-22 08:10:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_04"
down_revision: Union[str, None] = "20260322_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recurring_expenses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=True),
        sa.Column("expense_category_id", sa.UUID(), nullable=True),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["expense_category_id"], ["expense_categories.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recurring_expenses_account_id"), "recurring_expenses", ["account_id"], unique=False)
    op.create_index(op.f("ix_recurring_expenses_expense_category_id"), "recurring_expenses", ["expense_category_id"], unique=False)
    op.create_index(op.f("ix_recurring_expenses_vendor_id"), "recurring_expenses", ["vendor_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recurring_expenses_vendor_id"), table_name="recurring_expenses")
    op.drop_index(op.f("ix_recurring_expenses_expense_category_id"), table_name="recurring_expenses")
    op.drop_index(op.f("ix_recurring_expenses_account_id"), table_name="recurring_expenses")
    op.drop_table("recurring_expenses")
