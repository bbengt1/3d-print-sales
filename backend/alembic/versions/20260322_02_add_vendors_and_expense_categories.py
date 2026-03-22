"""add vendors and expense categories

Revision ID: 20260322_02
Revises: 20260322_01
Create Date: 2026-03-22 07:45:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_02"
down_revision: Union[str, None] = "20260322_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_vendors_name"), "vendors", ["name"], unique=False)

    op.create_table(
        "expense_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_expense_categories_name"), "expense_categories", ["name"], unique=False)
    op.create_index(op.f("ix_expense_categories_account_id"), "expense_categories", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_expense_categories_account_id"), table_name="expense_categories")
    op.drop_index(op.f("ix_expense_categories_name"), table_name="expense_categories")
    op.drop_table("expense_categories")

    op.drop_index(op.f("ix_vendors_name"), table_name="vendors")
    op.drop_table("vendors")
