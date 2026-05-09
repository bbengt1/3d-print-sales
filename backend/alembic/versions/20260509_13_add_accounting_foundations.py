"""recurring_journal_entries + Suspense/OpeningBalance COA seed (#260)

Revision ID: 20260509_13
Revises: 20260509_12
Create Date: 2026-05-10 00:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_13"
down_revision = "20260509_12"
branch_labels = None
depends_on = None


NEW_ACCOUNTS = [
    ("1900", "Suspense", "asset", "debit"),
    ("3300", "Opening Balance Equity", "equity", "credit"),
]


def upgrade() -> None:
    op.create_table(
        "recurring_journal_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("cadence", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("interval_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_on", sa.Date(), nullable=False),
        sa.Column("next_run_on", sa.Date(), nullable=False),
        sa.Column("last_run_on", sa.Date(), nullable=True),
        sa.Column("end_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("lines_template", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_journal_entries_name", "recurring_journal_entries", ["name"])
    op.create_index("ix_recurring_journal_entries_next_run_on", "recurring_journal_entries", ["next_run_on"])
    op.create_index("ix_recurring_journal_entries_is_active", "recurring_journal_entries", ["is_active"])

    op.create_table(
        "recurring_journal_entry_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recurring_je_id", sa.UUID(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("generated_journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recurring_je_id"], ["recurring_journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurring_journal_entry_runs_recurring_je_id",
        "recurring_journal_entry_runs",
        ["recurring_je_id"],
    )

    bind = op.get_bind()
    for code, name, account_type, normal_balance in NEW_ACCOUNTS:
        existing = bind.execute(
            sa.text("SELECT 1 FROM accounts WHERE code = :code"),
            {"code": code},
        ).first()
        if existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO accounts (id, code, name, account_type, normal_balance, "
                "is_active, is_system, is_bank_account, created_at, updated_at) "
                "VALUES (:id, :code, :name, :type, :normal, true, true, false, NOW(), NOW())"
            ),
            {
                "id": str(uuid.uuid4()),
                "code": code,
                "name": name,
                "type": account_type,
                "normal": normal_balance,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_recurring_journal_entry_runs_recurring_je_id", table_name="recurring_journal_entry_runs")
    op.drop_table("recurring_journal_entry_runs")
    op.drop_index("ix_recurring_journal_entries_is_active", table_name="recurring_journal_entries")
    op.drop_index("ix_recurring_journal_entries_next_run_on", table_name="recurring_journal_entries")
    op.drop_index("ix_recurring_journal_entries_name", table_name="recurring_journal_entries")
    op.drop_table("recurring_journal_entries")
