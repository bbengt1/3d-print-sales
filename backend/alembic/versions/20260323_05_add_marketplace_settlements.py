"""add marketplace settlements

Revision ID: 20260323_05
Revises: 20260323_04
Create Date: 2026-03-23 07:50:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260323_05"
down_revision: Union[str, None] = "20260323_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketplace_settlements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("settlement_number", sa.String(length=60), nullable=False),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("payout_date", sa.Date(), nullable=False),
        sa.Column("gross_sales", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("marketplace_fees", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("adjustments", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("reserves_held", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_deposit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expected_net", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discrepancy_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["sales_channels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marketplace_settlements_channel_id"), "marketplace_settlements", ["channel_id"], unique=False)
    op.create_index(op.f("ix_marketplace_settlements_settlement_number"), "marketplace_settlements", ["settlement_number"], unique=True)

    op.create_table(
        "settlement_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("settlement_id", sa.UUID(), nullable=False),
        sa.Column("sale_id", sa.UUID(), nullable=True),
        sa.Column("line_type", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.ForeignKeyConstraint(["settlement_id"], ["marketplace_settlements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_settlement_lines_sale_id"), "settlement_lines", ["sale_id"], unique=False)
    op.create_index(op.f("ix_settlement_lines_settlement_id"), "settlement_lines", ["settlement_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_settlement_lines_settlement_id"), table_name="settlement_lines")
    op.drop_index(op.f("ix_settlement_lines_sale_id"), table_name="settlement_lines")
    op.drop_table("settlement_lines")
    op.drop_index(op.f("ix_marketplace_settlements_settlement_number"), table_name="marketplace_settlements")
    op.drop_index(op.f("ix_marketplace_settlements_channel_id"), table_name="marketplace_settlements")
    op.drop_table("marketplace_settlements")
