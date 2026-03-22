"""add bills and bill payments

Revision ID: 20260322_03
Revises: 20260322_02
Create Date: 2026-03-22 07:55:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_03"
down_revision: Union[str, None] = "20260322_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("vendor_id", sa.UUID(), nullable=True),
        sa.Column("expense_category_id", sa.UUID(), nullable=True),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("bill_number", sa.String(length=60), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["expense_category_id"], ["expense_categories.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bills_vendor_id"), "bills", ["vendor_id"], unique=False)
    op.create_index(op.f("ix_bills_expense_category_id"), "bills", ["expense_category_id"], unique=False)
    op.create_index(op.f("ix_bills_account_id"), "bills", ["account_id"], unique=False)
    op.create_index(op.f("ix_bills_status"), "bills", ["status"], unique=False)

    op.create_table(
        "bill_payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("bill_id", sa.UUID(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("reference_number", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bill_payments_bill_id"), "bill_payments", ["bill_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bill_payments_bill_id"), table_name="bill_payments")
    op.drop_table("bill_payments")

    op.drop_index(op.f("ix_bills_status"), table_name="bills")
    op.drop_index(op.f("ix_bills_account_id"), table_name="bills")
    op.drop_index(op.f("ix_bills_expense_category_id"), table_name="bills")
    op.drop_index(op.f("ix_bills_vendor_id"), table_name="bills")
    op.drop_table("bills")
