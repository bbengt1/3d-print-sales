"""add cameras table

Revision ID: 20260412_01
Revises: 20260329_03
Create Date: 2026-04-12 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_01"
down_revision = "20260329_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("go2rtc_base_url", sa.String(length=500), nullable=False),
        sa.Column("stream_name", sa.String(length=120), nullable=False),
        sa.Column("printer_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("printer_id", name="uq_cameras_printer_id"),
    )
    op.create_index(op.f("ix_cameras_name"), "cameras", ["name"], unique=True)
    op.create_index(op.f("ix_cameras_slug"), "cameras", ["slug"], unique=True)
    op.create_index(op.f("ix_cameras_is_active"), "cameras", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cameras_is_active"), table_name="cameras")
    op.drop_index(op.f("ix_cameras_slug"), table_name="cameras")
    op.drop_index(op.f("ix_cameras_name"), table_name="cameras")
    op.drop_table("cameras")
