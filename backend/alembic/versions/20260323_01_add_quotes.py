"""add quotes

Revision ID: 20260323_01
Revises: 20260322_04
Create Date: 2026-03-23 04:58:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260323_01"
down_revision: Union[str, None] = "20260322_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quote_number", sa.String(length=50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("qty_per_plate", sa.Integer(), nullable=False),
        sa.Column("num_plates", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=False),
        sa.Column("total_pieces", sa.Integer(), nullable=False),
        sa.Column("material_per_plate_g", sa.Numeric(10, 2), nullable=False),
        sa.Column("print_time_per_plate_hrs", sa.Numeric(10, 2), nullable=False),
        sa.Column("labor_mins", sa.Numeric(10, 2), nullable=False),
        sa.Column("design_time_hrs", sa.Numeric(10, 2), nullable=True),
        sa.Column("electricity_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("material_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("labor_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("design_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("machine_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("packaging_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("shipping_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("failure_buffer", sa.Numeric(10, 4), nullable=False),
        sa.Column("subtotal_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("overhead", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("cost_per_piece", sa.Numeric(10, 4), nullable=False),
        sa.Column("target_margin_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("price_per_piece", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_revenue", sa.Numeric(10, 4), nullable=False),
        sa.Column("platform_fees", sa.Numeric(10, 4), nullable=False),
        sa.Column("net_profit", sa.Numeric(10, 4), nullable=False),
        sa.Column("profit_per_piece", sa.Numeric(10, 4), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quotes_quote_number"), "quotes", ["quote_number"], unique=True)
    op.create_index(op.f("ix_quotes_status"), "quotes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quotes_status"), table_name="quotes")
    op.drop_index(op.f("ix_quotes_quote_number"), table_name="quotes")
    op.drop_table("quotes")
