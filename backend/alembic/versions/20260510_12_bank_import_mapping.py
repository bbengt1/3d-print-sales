"""#315 P2: per-bank-account CSV column mapping

Revision ID: 20260510_12
Revises: 20260510_11
Create Date: 2026-05-10 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_12"
down_revision = "20260510_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_import_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_bank_import_mapping_account"),
    )


def downgrade() -> None:
    op.drop_table("bank_import_mappings")
