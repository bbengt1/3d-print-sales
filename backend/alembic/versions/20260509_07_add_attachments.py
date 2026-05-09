"""add attachments table (#250)

Revision ID: 20260509_07
Revises: 20260509_06
Create Date: 2026-05-09 22:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_07"
down_revision = "20260509_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_storage_key", sa.String(length=500), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.UUID(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_scope", "attachments", ["scope"])
    op.create_index("ix_attachments_record_id", "attachments", ["record_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])
    op.create_index("ix_attachments_deleted_at", "attachments", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_attachments_deleted_at", table_name="attachments")
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_record_id", table_name="attachments")
    op.drop_index("ix_attachments_scope", table_name="attachments")
    op.drop_table("attachments")
