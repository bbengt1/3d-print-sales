"""add account_budgets (#259)

Revision ID: 20260509_16
Revises: 20260509_15
Create Date: 2026-05-10 01:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_16"
down_revision = "20260509_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "year", "month", name="uq_account_budgets_acct_yr_mo"),
    )
    op.create_index("ix_account_budgets_account_id", "account_budgets", ["account_id"])
    op.create_index("ix_account_budgets_year", "account_budgets", ["year"])
    op.create_index("ix_account_budgets_month", "account_budgets", ["month"])


def downgrade() -> None:
    op.drop_index("ix_account_budgets_month", table_name="account_budgets")
    op.drop_index("ix_account_budgets_year", table_name="account_budgets")
    op.drop_index("ix_account_budgets_account_id", table_name="account_budgets")
    op.drop_table("account_budgets")
