"""#318 P2: add fulfillment_location_id to sales

Revision ID: 20260510_03
Revises: 20260510_02
Create Date: 2026-05-10 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_03"
down_revision = "20260510_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales") as batch:
        batch.add_column(sa.Column("fulfillment_location_id", sa.UUID(), nullable=True))
        batch.create_foreign_key(
            "fk_sales_fulfillment_location",
            "inventory_locations",
            ["fulfillment_location_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("sales") as batch:
        batch.drop_constraint("fk_sales_fulfillment_location", type_="foreignkey")
        batch.drop_column("fulfillment_location_id")
