"""add supply bom components

Revision ID: 20260508_02
Revises: 20260508_01
Create Date: 2026-05-08 15:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_02"
down_revision = "20260508_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_bom_items", sa.Column("component_name", sa.String(length=200), nullable=True))
    op.add_column("product_bom_items", sa.Column("component_sku", sa.String(length=100), nullable=True))
    op.add_column("product_bom_items", sa.Column("unit_cost", sa.Numeric(12, 4), nullable=True))
    op.add_column("product_bom_items", sa.Column("available_quantity", sa.Numeric(12, 4), nullable=True))

    op.drop_constraint("ck_product_bom_items_component_target", "product_bom_items", type_="check")
    op.create_check_constraint(
        "ck_product_bom_items_component_target",
        "product_bom_items",
        "((component_type = 'material' AND material_id IS NOT NULL AND component_product_id IS NULL "
        "AND component_name IS NULL) OR "
        "(component_type = 'product' AND component_product_id IS NOT NULL AND material_id IS NULL "
        "AND component_name IS NULL) OR "
        "(component_type = 'supply' AND component_name IS NOT NULL AND material_id IS NULL "
        "AND component_product_id IS NULL))",
    )
    op.create_check_constraint(
        "ck_product_bom_items_unit_cost_nonnegative",
        "product_bom_items",
        "unit_cost IS NULL OR unit_cost >= 0",
    )
    op.create_check_constraint(
        "ck_product_bom_items_available_nonnegative",
        "product_bom_items",
        "available_quantity IS NULL OR available_quantity >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_product_bom_items_available_nonnegative", "product_bom_items", type_="check")
    op.drop_constraint("ck_product_bom_items_unit_cost_nonnegative", "product_bom_items", type_="check")
    op.drop_constraint("ck_product_bom_items_component_target", "product_bom_items", type_="check")
    op.create_check_constraint(
        "ck_product_bom_items_component_target",
        "product_bom_items",
        "((component_type = 'material' AND material_id IS NOT NULL AND component_product_id IS NULL) OR "
        "(component_type = 'product' AND component_product_id IS NOT NULL AND material_id IS NULL))",
    )

    op.drop_column("product_bom_items", "available_quantity")
    op.drop_column("product_bom_items", "unit_cost")
    op.drop_column("product_bom_items", "component_sku")
    op.drop_column("product_bom_items", "component_name")
