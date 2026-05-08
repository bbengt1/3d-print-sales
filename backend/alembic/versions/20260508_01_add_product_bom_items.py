"""add product bom items

Revision ID: 20260508_01
Revises: 20260420_01
Create Date: 2026-05-08 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_01"
down_revision = "20260420_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_bom_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("component_type", sa.String(length=20), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=True),
        sa.Column("component_product_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="each"),
        sa.Column("waste_factor_pct", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_product_bom_items_quantity_positive"),
        sa.CheckConstraint("waste_factor_pct >= 0", name="ck_product_bom_items_waste_nonnegative"),
        sa.CheckConstraint(
            "((component_type = 'material' AND material_id IS NOT NULL AND component_product_id IS NULL) OR "
            "(component_type = 'product' AND component_product_id IS NOT NULL AND material_id IS NULL))",
            name="ck_product_bom_items_component_target",
        ),
        sa.ForeignKeyConstraint(["component_product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_bom_items_product_id", "product_bom_items", ["product_id"])
    op.create_index("ix_product_bom_items_material_id", "product_bom_items", ["material_id"])
    op.create_index("ix_product_bom_items_component_product_id", "product_bom_items", ["component_product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_bom_items_component_product_id", table_name="product_bom_items")
    op.drop_index("ix_product_bom_items_material_id", table_name="product_bom_items")
    op.drop_index("ix_product_bom_items_product_id", table_name="product_bom_items")
    op.drop_table("product_bom_items")
