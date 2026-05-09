"""add inventory_locations and inventory_transfers (Phase 1 of #245)

Revision ID: 20260509_05
Revises: 20260509_04
Create Date: 2026-05-09 20:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_05"
down_revision = "20260509_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False, server_default="internal"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_inventory_locations_name"),
    )
    op.create_index("ix_inventory_locations_kind", "inventory_locations", ["kind"])

    # Seed the Default location.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO inventory_locations (id, name, kind, is_active, created_at, updated_at) "
            "VALUES (:id, 'Default', 'internal', true, NOW(), NOW())"
        ),
        {"id": str(uuid.uuid4())},
    )

    op.create_table(
        "inventory_transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transfer_number", sa.String(length=50), nullable=False),
        sa.Column("from_location_id", sa.UUID(), nullable=False),
        sa.Column("to_location_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transferred_by_user_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["from_location_id"], ["inventory_locations.id"]),
        sa.ForeignKeyConstraint(["to_location_id"], ["inventory_locations.id"]),
        sa.ForeignKeyConstraint(["transferred_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transfer_number", name="uq_inventory_transfers_transfer_number"),
    )
    op.create_index("ix_inventory_transfers_status", "inventory_transfers", ["status"])

    op.create_table(
        "inventory_transfer_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transfer_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("material_id", sa.UUID(), nullable=True),
        sa.Column("supply_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["transfer_id"], ["inventory_transfers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["supply_id"], ["supplies.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_transfer_lines_transfer_id",
        "inventory_transfer_lines",
        ["transfer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_transfer_lines_transfer_id", table_name="inventory_transfer_lines")
    op.drop_table("inventory_transfer_lines")
    op.drop_index("ix_inventory_transfers_status", table_name="inventory_transfers")
    op.drop_table("inventory_transfers")
    op.drop_index("ix_inventory_locations_kind", table_name="inventory_locations")
    op.drop_table("inventory_locations")
