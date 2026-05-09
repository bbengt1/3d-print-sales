"""add custom_field_definitions + custom_field_values (#253)

Revision ID: 20260509_17
Revises: 20260509_16
Create Date: 2026-05-10 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_17"
down_revision = "20260509_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=20), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key", name="uq_custom_field_definitions_scope_key"),
    )
    op.create_index("ix_custom_field_definitions_scope", "custom_field_definitions", ["scope"])
    op.create_index("ix_custom_field_definitions_is_active", "custom_field_definitions", ["is_active"])

    op.create_table(
        "custom_field_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["definition_id"], ["custom_field_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "record_id", name="uq_custom_field_values_def_record"),
    )
    op.create_index("ix_custom_field_values_definition_id", "custom_field_values", ["definition_id"])
    op.create_index("ix_custom_field_values_record_id", "custom_field_values", ["record_id"])


def downgrade() -> None:
    op.drop_index("ix_custom_field_values_record_id", table_name="custom_field_values")
    op.drop_index("ix_custom_field_values_definition_id", table_name="custom_field_values")
    op.drop_table("custom_field_values")
    op.drop_index("ix_custom_field_definitions_is_active", table_name="custom_field_definitions")
    op.drop_index("ix_custom_field_definitions_scope", table_name="custom_field_definitions")
    op.drop_table("custom_field_definitions")
