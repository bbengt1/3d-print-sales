"""add material receipts

Revision ID: 20260322_01
Revises: 20260321_01
Create Date: 2026-03-22 06:40:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_01"
down_revision: Union[str, None] = "20260321_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=False),
        sa.Column("vendor_name", sa.String(length=120), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("receipt_number", sa.String(length=60), nullable=True),
        sa.Column("quantity_purchased_g", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity_remaining_g", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost_per_g", sa.Numeric(12, 6), nullable=False),
        sa.Column("landed_cost_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("landed_cost_per_g", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("valuation_method", sa.String(length=20), nullable=False, server_default="lot"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_material_receipts_material_id"), "material_receipts", ["material_id"], unique=False)
    op.create_index(op.f("ix_material_receipts_vendor_name"), "material_receipts", ["vendor_name"], unique=False)
    op.create_index(op.f("ix_material_receipts_purchase_date"), "material_receipts", ["purchase_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_material_receipts_purchase_date"), table_name="material_receipts")
    op.drop_index(op.f("ix_material_receipts_vendor_name"), table_name="material_receipts")
    op.drop_index(op.f("ix_material_receipts_material_id"), table_name="material_receipts")
    op.drop_table("material_receipts")
