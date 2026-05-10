"""#331 P2: form_templates table

Revision ID: 20260510_06
Revises: 20260510_05
Create Date: 2026-05-10 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_06"
down_revision = "20260510_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("defaults", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_form_templates_scope", "form_templates", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_form_templates_scope", table_name="form_templates")
    op.drop_table("form_templates")
