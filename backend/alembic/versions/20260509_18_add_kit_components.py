"""add kit_components (#262 Phase 1)

Revision ID: 20260509_18
Revises: 20260509_17
Create Date: 2026-05-10 02:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_18"
down_revision = "20260509_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kit_components",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kit_product_id", sa.UUID(), nullable=False),
        sa.Column("component_product_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["kit_product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["component_product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kit_product_id", "component_product_id", name="uq_kit_components_kit_component"),
    )
    op.create_index("ix_kit_components_kit_product_id", "kit_components", ["kit_product_id"])
    op.create_index("ix_kit_components_component_product_id", "kit_components", ["component_product_id"])


def downgrade() -> None:
    op.drop_index("ix_kit_components_component_product_id", table_name="kit_components")
    op.drop_index("ix_kit_components_kit_product_id", table_name="kit_components")
    op.drop_table("kit_components")
