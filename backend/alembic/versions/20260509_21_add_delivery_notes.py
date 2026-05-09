"""add delivery_notes (#263 Phase 1 — delivery-notes piece)

Revision ID: 20260509_21
Revises: 20260509_20
Create Date: 2026-05-10 04:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_21"
down_revision = "20260509_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("delivery_note_number", sa.String(length=50), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=True),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("shipped_on", sa.Date(), nullable=True),
        sa.Column("tracking_number", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_note_number", name="uq_delivery_notes_number"),
    )
    op.create_index("ix_delivery_notes_status", "delivery_notes", ["status"])
    op.create_index("ix_delivery_notes_invoice_id", "delivery_notes", ["invoice_id"])

    op.create_table(
        "delivery_note_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("delivery_note_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["delivery_note_id"], ["delivery_notes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_note_lines_delivery_note_id", "delivery_note_lines", ["delivery_note_id"])


def downgrade() -> None:
    op.drop_table("delivery_note_lines")
    op.drop_table("delivery_notes")
