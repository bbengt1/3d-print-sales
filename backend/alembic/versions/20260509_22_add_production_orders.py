"""add production_orders + consumptions + finished_goods_layers (#242 Phase 1)

Revision ID: 20260509_22
Revises: 20260509_21
Create Date: 2026-05-10 05:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_22"
down_revision = "20260509_21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("output_quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_material_cost", sa.Numeric(14, 4), nullable=True),
        sa.Column("applied_overhead", sa.Numeric(14, 4), nullable=True),
        sa.Column("total_finished_goods_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number", name="uq_production_orders_number"),
    )
    op.create_index("ix_production_orders_status", "production_orders", ["status"])
    op.create_index("ix_production_orders_product_id", "production_orders", ["product_id"])

    op.create_table(
        "production_order_consumptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("production_order_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=True),
        sa.Column("supply_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("planned_qty", sa.Numeric(14, 4), nullable=False),
        sa.Column("actual_qty", sa.Numeric(14, 4), nullable=True),
        sa.Column("actual_unit_cost", sa.Numeric(14, 6), nullable=True),
        sa.Column("actual_total_cost", sa.Numeric(14, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["supply_id"], ["supplies.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_order_consumptions_production_order_id", "production_order_consumptions", ["production_order_id"])

    op.create_table(
        "finished_goods_layers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("production_order_id", sa.UUID(), nullable=True),
        sa.Column("qty_total", sa.Numeric(14, 4), nullable=False),
        sa.Column("qty_remaining", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finished_goods_layers_product_id", "finished_goods_layers", ["product_id"])
    op.create_index("ix_finished_goods_layers_production_order_id", "finished_goods_layers", ["production_order_id"])


def downgrade() -> None:
    op.drop_table("finished_goods_layers")
    op.drop_table("production_order_consumptions")
    op.drop_table("production_orders")
