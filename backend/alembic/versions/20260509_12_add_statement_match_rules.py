"""add statement_match_rules (#241)

Revision ID: 20260509_12
Revises: 20260509_11
Create Date: 2026-05-09 23:58:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_12"
down_revision = "20260509_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "statement_match_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("match_type", sa.String(length=20), nullable=False),
        sa.Column("match_pattern", sa.String(length=500), nullable=False),
        sa.Column("match_amount_sign", sa.String(length=10), nullable=False, server_default="any"),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_statement_match_rules_account_id", "statement_match_rules", ["account_id"])
    op.create_index("ix_statement_match_rules_priority", "statement_match_rules", ["priority"])
    op.create_index("ix_statement_match_rules_is_active", "statement_match_rules", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_statement_match_rules_is_active", table_name="statement_match_rules")
    op.drop_index("ix_statement_match_rules_priority", table_name="statement_match_rules")
    op.drop_index("ix_statement_match_rules_account_id", table_name="statement_match_rules")
    op.drop_table("statement_match_rules")
