"""add supply inventory

Revision ID: 20260508_03
Revises: 20260508_02
Create Date: 2026-05-08 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_03"
down_revision = "20260508_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="each"),
        sa.Column("unit_cost", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("quantity_on_hand", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("reorder_point", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("supplier", sa.String(length=200), nullable=True),
        sa.Column("supplier_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("unit_cost >= 0", name="ck_supplies_unit_cost_nonnegative"),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_supplies_quantity_nonnegative"),
        sa.CheckConstraint("reorder_point >= 0", name="ck_supplies_reorder_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="uq_supplies_sku"),
    )
    op.create_index("ix_supplies_active", "supplies", ["active"])
    op.create_index("ix_supplies_category", "supplies", ["category"])

    op.add_column("product_bom_items", sa.Column("supply_id", sa.UUID(), nullable=True))
    op.create_index("ix_product_bom_items_supply_id", "product_bom_items", ["supply_id"])
    op.create_foreign_key(
        "fk_product_bom_items_supply_id_supplies",
        "product_bom_items",
        "supplies",
        ["supply_id"],
        ["id"],
    )

    op.drop_constraint("ck_product_bom_items_component_target", "product_bom_items", type_="check")
    op.create_check_constraint(
        "ck_product_bom_items_component_target",
        "product_bom_items",
        "((component_type = 'material' AND material_id IS NOT NULL AND component_product_id IS NULL "
        "AND supply_id IS NULL AND component_name IS NULL) OR "
        "(component_type = 'product' AND component_product_id IS NOT NULL AND material_id IS NULL "
        "AND supply_id IS NULL AND component_name IS NULL) OR "
        "(component_type = 'supply' AND material_id IS NULL AND component_product_id IS NULL "
        "AND ((supply_id IS NOT NULL AND component_name IS NULL) OR "
        "(supply_id IS NULL AND component_name IS NOT NULL))))",
    )


def downgrade() -> None:
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
    op.drop_constraint("fk_product_bom_items_supply_id_supplies", "product_bom_items", type_="foreignkey")
    op.drop_index("ix_product_bom_items_supply_id", table_name="product_bom_items")
    op.drop_column("product_bom_items", "supply_id")

    op.drop_index("ix_supplies_category", table_name="supplies")
    op.drop_index("ix_supplies_active", table_name="supplies")
    op.drop_table("supplies")
