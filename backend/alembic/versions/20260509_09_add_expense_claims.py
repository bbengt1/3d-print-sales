"""add expense_claims and Owner Reimbursable Liability seed (#251)

Revision ID: 20260509_09
Revises: 20260509_08
Create Date: 2026-05-09 23:30:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_09"
down_revision = "20260509_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_claims",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_number", sa.String(length=50), nullable=False),
        sa.Column("payer_kind", sa.String(length=30), nullable=False, server_default="owner"),
        sa.Column("payer_name", sa.String(length=200), nullable=False),
        sa.Column("submitted_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("reimbursement_journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.ForeignKeyConstraint(["reimbursement_journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_number", name="uq_expense_claims_claim_number"),
    )
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"])

    op.create_table(
        "expense_claim_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("expense_account_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["expense_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_claim_lines_claim_id", "expense_claim_lines", ["claim_id"])

    # Seed Owner Reimbursable Liability (idempotent)
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM accounts WHERE code = '2300'")
    ).first()
    if not existing:
        bind.execute(
            sa.text(
                "INSERT INTO accounts (id, code, name, account_type, normal_balance, "
                "is_active, is_system, is_bank_account, created_at, updated_at) "
                "VALUES (:id, '2300', 'Owner Reimbursable Liability', 'liability', 'credit', "
                "true, true, false, NOW(), NOW())"
            ),
            {"id": str(uuid.uuid4())},
        )


def downgrade() -> None:
    op.drop_index("ix_expense_claim_lines_claim_id", table_name="expense_claim_lines")
    op.drop_table("expense_claim_lines")
    op.drop_index("ix_expense_claims_status", table_name="expense_claims")
    op.drop_table("expense_claims")
