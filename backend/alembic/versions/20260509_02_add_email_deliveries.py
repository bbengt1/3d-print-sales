"""add email_deliveries audit table

Revision ID: 20260509_02
Revises: 20260509_01
Create Date: 2026-05-09 17:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_02"
down_revision = "20260509_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("cc", sa.String(length=1000), nullable=True),
        sa.Column("bcc", sa.String(length=1000), nullable=True),
        sa.Column("from_email", sa.String(length=320), nullable=False),
        sa.Column("from_name", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("transport", sa.String(length=20), nullable=False),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_by_user_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_deliveries_scope", "email_deliveries", ["scope"])
    op.create_index("ix_email_deliveries_record_id", "email_deliveries", ["record_id"])
    op.create_index("ix_email_deliveries_provider_message_id", "email_deliveries", ["provider_message_id"])
    op.create_index("ix_email_deliveries_status", "email_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_email_deliveries_status", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_provider_message_id", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_record_id", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_scope", table_name="email_deliveries")
    op.drop_table("email_deliveries")
