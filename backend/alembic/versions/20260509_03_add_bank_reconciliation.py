"""add bank account typing, journal_line.cleared_status, and bank reconciliation tables

Revision ID: 20260509_03
Revises: 20260509_02
Create Date: 2026-05-09 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_03"
down_revision = "20260509_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Account.is_bank_account + Account.bank_account_kind
    op.add_column(
        "accounts",
        sa.Column("is_bank_account", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "accounts",
        sa.Column("bank_account_kind", sa.String(length=30), nullable=True),
    )
    op.create_index("ix_accounts_is_bank_account", "accounts", ["is_bank_account"])

    # JournalLine.cleared_status
    op.add_column(
        "journal_lines",
        sa.Column(
            "cleared_status",
            sa.String(length=15),
            nullable=False,
            server_default="uncleared",
        ),
    )
    op.create_index("ix_journal_lines_cleared_status", "journal_lines", ["cleared_status"])

    # BankReconciliation
    op.create_table(
        "bank_reconciliations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("statement_end_date", sa.Date(), nullable=False),
        sa.Column("statement_ending_balance", sa.Numeric(14, 4), nullable=False),
        sa.Column("opening_balance", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by_user_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["finalized_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_reconciliations_account_id", "bank_reconciliations", ["account_id"])
    op.create_index("ix_bank_reconciliations_status", "bank_reconciliations", ["status"])

    # BankReconciliationLine
    op.create_table(
        "bank_reconciliation_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reconciliation_id", sa.UUID(), nullable=False),
        sa.Column("journal_line_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["reconciliation_id"], ["bank_reconciliations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journal_line_id"], ["journal_lines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_id", "journal_line_id",
            name="uq_bank_reconciliation_lines_recon_line",
        ),
    )
    op.create_index(
        "ix_bank_reconciliation_lines_reconciliation_id",
        "bank_reconciliation_lines",
        ["reconciliation_id"],
    )
    op.create_index(
        "ix_bank_reconciliation_lines_journal_line_id",
        "bank_reconciliation_lines",
        ["journal_line_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_reconciliation_lines_journal_line_id", table_name="bank_reconciliation_lines")
    op.drop_index("ix_bank_reconciliation_lines_reconciliation_id", table_name="bank_reconciliation_lines")
    op.drop_table("bank_reconciliation_lines")

    op.drop_index("ix_bank_reconciliations_status", table_name="bank_reconciliations")
    op.drop_index("ix_bank_reconciliations_account_id", table_name="bank_reconciliations")
    op.drop_table("bank_reconciliations")

    op.drop_index("ix_journal_lines_cleared_status", table_name="journal_lines")
    op.drop_column("journal_lines", "cleared_status")

    op.drop_index("ix_accounts_is_bank_account", table_name="accounts")
    op.drop_column("accounts", "bank_account_kind")
    op.drop_column("accounts", "is_bank_account")
