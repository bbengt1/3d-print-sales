"""add recurring_invoices and recurring_invoice_runs (#247)

Revision ID: 20260509_08
Revises: 20260509_07
Create Date: 2026-05-09 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_08"
down_revision = "20260509_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("cadence", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("interval_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_on", sa.Date(), nullable=False),
        sa.Column("next_run_on", sa.Date(), nullable=False),
        sa.Column("last_run_on", sa.Date(), nullable=True),
        sa.Column("end_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("line_items_template", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("due_in_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_invoices_name", "recurring_invoices", ["name"])
    op.create_index("ix_recurring_invoices_customer_id", "recurring_invoices", ["customer_id"])
    op.create_index("ix_recurring_invoices_next_run_on", "recurring_invoices", ["next_run_on"])
    op.create_index("ix_recurring_invoices_is_active", "recurring_invoices", ["is_active"])

    op.create_table(
        "recurring_invoice_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recurring_invoice_id", sa.UUID(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("generated_invoice_id", sa.UUID(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recurring_invoice_id"], ["recurring_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurring_invoice_runs_recurring_invoice_id",
        "recurring_invoice_runs",
        ["recurring_invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recurring_invoice_runs_recurring_invoice_id", table_name="recurring_invoice_runs")
    op.drop_table("recurring_invoice_runs")
    op.drop_index("ix_recurring_invoices_is_active", table_name="recurring_invoices")
    op.drop_index("ix_recurring_invoices_next_run_on", table_name="recurring_invoices")
    op.drop_index("ix_recurring_invoices_customer_id", table_name="recurring_invoices")
    op.drop_index("ix_recurring_invoices_name", table_name="recurring_invoices")
    op.drop_table("recurring_invoices")
