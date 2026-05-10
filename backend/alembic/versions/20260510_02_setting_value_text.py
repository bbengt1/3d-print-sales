"""#320 P2: bump settings.value to TEXT for editable templates

Revision ID: 20260510_02
Revises: 20260510_01
Create Date: 2026-05-10 11:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_02"
down_revision = "20260510_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch:
        batch.alter_column("value", existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch:
        # Truncation possible if any current value exceeds 255 chars; downgrade is best-effort.
        batch.alter_column("value", existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=False)
