"""add statement_imports and statement_lines (#240)

Revision ID: 20260509_11
Revises: 20260509_10
Create Date: 2026-05-09 23:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_11"
down_revision = "20260509_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "statement_imports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("source_format", sa.String(length=10), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_review"),
        sa.Column("imported_by_user_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_statement_imports_account_id", "statement_imports", ["account_id"])
    op.create_index("ix_statement_imports_status", "statement_imports", ["status"])

    op.create_table(
        "statement_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("import_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("posted_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("fitid", sa.String(length=120), nullable=True),
        sa.Column("matched_journal_line_id", sa.UUID(), nullable=True),
        sa.Column("match_status", sa.String(length=20), nullable=False, server_default="unmatched"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["import_id"], ["statement_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["matched_journal_line_id"], ["journal_lines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "fitid", name="uq_statement_lines_account_fitid"),
    )
    op.create_index("ix_statement_lines_import_id", "statement_lines", ["import_id"])
    op.create_index("ix_statement_lines_account_id", "statement_lines", ["account_id"])
    op.create_index("ix_statement_lines_posted_date", "statement_lines", ["posted_date"])
    op.create_index("ix_statement_lines_match_status", "statement_lines", ["match_status"])


def downgrade() -> None:
    op.drop_index("ix_statement_lines_match_status", table_name="statement_lines")
    op.drop_index("ix_statement_lines_posted_date", table_name="statement_lines")
    op.drop_index("ix_statement_lines_account_id", table_name="statement_lines")
    op.drop_index("ix_statement_lines_import_id", table_name="statement_lines")
    op.drop_table("statement_lines")
    op.drop_index("ix_statement_imports_status", table_name="statement_imports")
    op.drop_index("ix_statement_imports_account_id", table_name="statement_imports")
    op.drop_table("statement_imports")
