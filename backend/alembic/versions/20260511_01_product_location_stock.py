"""#318 P2: product_location_stock SoT + backfill from Product.stock_qty

Revision ID: 20260511_01
Revises: 20260510_12
Create Date: 2026-05-11 09:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260511_01"
down_revision = "20260510_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_location_stock",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("on_hand_qty", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "location_id", name="uq_product_location_stock"),
    )
    op.create_index(
        "ix_product_location_stock_product_id",
        "product_location_stock",
        ["product_id"],
    )
    op.create_index(
        "ix_product_location_stock_location_id",
        "product_location_stock",
        ["location_id"],
    )

    # Backfill: park each product's existing stock_qty at the seeded Default
    # location, so per-location reads work immediately for single-location
    # operators. Skipped if no Default location exists yet (fresh installs
    # before `ensure_default_location` has been called).
    bind = op.get_bind()
    default_loc = bind.execute(
        sa.text("SELECT id FROM inventory_locations WHERE name = 'Default' LIMIT 1")
    ).first()
    if default_loc is None:
        return

    default_loc_id = default_loc[0]
    products = bind.execute(
        sa.text(
            "SELECT id, stock_qty FROM products "
            "WHERE stock_qty IS NOT NULL AND stock_qty <> 0"
        )
    ).fetchall()
    for product_id, stock_qty in products:
        bind.execute(
            sa.text(
                "INSERT INTO product_location_stock "
                "(id, product_id, location_id, on_hand_qty) "
                "VALUES (:id, :product_id, :location_id, :qty)"
            ),
            {
                "id": str(uuid.uuid4()),
                "product_id": str(product_id),
                "location_id": str(default_loc_id),
                "qty": stock_qty,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_product_location_stock_location_id", table_name="product_location_stock")
    op.drop_index("ix_product_location_stock_product_id", table_name="product_location_stock")
    op.drop_table("product_location_stock")
