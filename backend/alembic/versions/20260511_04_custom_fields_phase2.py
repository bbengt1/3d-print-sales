"""#326 P2: custom-fields formula column for computed fields

Revision ID: 20260511_04
Revises: 20260511_03
Create Date: 2026-05-11 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260511_04"
down_revision = "20260511_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("custom_field_definitions") as batch:
        batch.add_column(sa.Column("formula", sa.String(120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("custom_field_definitions") as batch:
        batch.drop_column("formula")
