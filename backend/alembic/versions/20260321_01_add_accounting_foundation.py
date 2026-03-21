"""add accounting foundation

Revision ID: 20260321_01
Revises: None
Create Date: 2026-03-21 15:55:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260321_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("normal_balance", sa.String(length=10), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_accounts_code"),
    )
    op.create_index(op.f("ix_accounts_code"), "accounts", ["code"], unique=False)
    op.create_index(op.f("ix_accounts_name"), "accounts", ["name"], unique=False)
    op.create_index(op.f("ix_accounts_account_type"), "accounts", ["account_type"], unique=False)

    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("is_adjustment_period", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_key", name="uq_accounting_periods_period_key"),
    )
    op.create_index(op.f("ix_accounting_periods_period_key"), "accounting_periods", ["period_key"], unique=False)

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entry_number", sa.String(length=50), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("accounting_period_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reversal_of_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["accounting_period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_number"),
    )
    op.create_index(op.f("ix_journal_entries_entry_number"), "journal_entries", ["entry_number"], unique=False)
    op.create_index(op.f("ix_journal_entries_entry_date"), "journal_entries", ["entry_date"], unique=False)
    op.create_index(op.f("ix_journal_entries_status"), "journal_entries", ["status"], unique=False)

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("journal_entry_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_journal_lines_journal_entry_id"), "journal_lines", ["journal_entry_id"], unique=False)
    op.create_index(op.f("ix_journal_lines_account_id"), "journal_lines", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_journal_lines_account_id"), table_name="journal_lines")
    op.drop_index(op.f("ix_journal_lines_journal_entry_id"), table_name="journal_lines")
    op.drop_table("journal_lines")

    op.drop_index(op.f("ix_journal_entries_status"), table_name="journal_entries")
    op.drop_index(op.f("ix_journal_entries_entry_date"), table_name="journal_entries")
    op.drop_index(op.f("ix_journal_entries_entry_number"), table_name="journal_entries")
    op.drop_table("journal_entries")

    op.drop_index(op.f("ix_accounting_periods_period_key"), table_name="accounting_periods")
    op.drop_table("accounting_periods")

    op.drop_index(op.f("ix_accounts_account_type"), table_name="accounts")
    op.drop_index(op.f("ix_accounts_name"), table_name="accounts")
    op.drop_index(op.f("ix_accounts_code"), table_name="accounts")
    op.drop_table("accounts")
