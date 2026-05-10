"""#230: discovered_via + discovery_metadata + needs_review on materials

Revision ID: 20260510_10
Revises: 20260510_09
Create Date: 2026-05-10 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_10"
down_revision = "20260510_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("materials") as batch:
        batch.add_column(sa.Column("discovered_via", sa.String(40), nullable=True))
        batch.add_column(sa.Column("discovery_metadata", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.create_index("ix_materials_discovered_via", "materials", ["discovered_via"])
    op.create_index("ix_materials_needs_review", "materials", ["needs_review"])


def downgrade() -> None:
    op.drop_index("ix_materials_needs_review", table_name="materials")
    op.drop_index("ix_materials_discovered_via", table_name="materials")
    with op.batch_alter_table("materials") as batch:
        batch.drop_column("needs_review")
        batch.drop_column("discovery_metadata")
        batch.drop_column("discovered_via")
