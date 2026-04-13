"""add sale shipping label fields

Revision ID: 20260413_01
Revises: 20260412_01
Create Date: 2026-04-13 10:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260413_01"
down_revision = "20260412_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("shipping_recipient_name", sa.String(length=200), nullable=True))
    op.add_column("sales", sa.Column("shipping_company", sa.String(length=200), nullable=True))
    op.add_column("sales", sa.Column("shipping_address_line1", sa.String(length=200), nullable=True))
    op.add_column("sales", sa.Column("shipping_address_line2", sa.String(length=200), nullable=True))
    op.add_column("sales", sa.Column("shipping_city", sa.String(length=120), nullable=True))
    op.add_column("sales", sa.Column("shipping_state", sa.String(length=120), nullable=True))
    op.add_column("sales", sa.Column("shipping_postal_code", sa.String(length=40), nullable=True))
    op.add_column("sales", sa.Column("shipping_country", sa.String(length=120), nullable=True))
    op.add_column("sales", sa.Column("shipping_label_generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales", sa.Column("shipping_label_last_printed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sales",
        sa.Column("shipping_label_print_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("sales", "shipping_label_print_count", server_default=None)


def downgrade() -> None:
    op.drop_column("sales", "shipping_label_print_count")
    op.drop_column("sales", "shipping_label_last_printed_at")
    op.drop_column("sales", "shipping_label_generated_at")
    op.drop_column("sales", "shipping_country")
    op.drop_column("sales", "shipping_postal_code")
    op.drop_column("sales", "shipping_state")
    op.drop_column("sales", "shipping_city")
    op.drop_column("sales", "shipping_address_line2")
    op.drop_column("sales", "shipping_address_line1")
    op.drop_column("sales", "shipping_company")
    op.drop_column("sales", "shipping_recipient_name")
