"""add journal_lines.posted_on and inter_account_transfers (#246)

Revision ID: 20260509_06
Revises: 20260509_05
Create Date: 2026-05-09 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_06"
down_revision = "20260509_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "journal_lines",
        sa.Column("posted_on", sa.Date(), nullable=True),
    )

    op.create_table(
        "inter_account_transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transfer_number", sa.String(length=50), nullable=False),
        sa.Column("from_account_id", sa.UUID(), nullable=False),
        sa.Column("to_account_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("journal_entry_id", sa.UUID(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["from_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["to_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transfer_number", name="uq_inter_account_transfers_transfer_number"),
    )


def downgrade() -> None:
    op.drop_table("inter_account_transfers")
    op.drop_column("journal_lines", "posted_on")
