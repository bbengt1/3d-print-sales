"""add credit/debit notes + COA seed (#248)

Revision ID: 20260509_19
Revises: 20260509_18
Create Date: 2026-05-10 03:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_19"
down_revision = "20260509_18"
branch_labels = None
depends_on = None


NEW_ACCOUNTS = [
    ("4800", "Sales Returns", "revenue", "debit"),
    ("5400", "Purchase Returns", "cogs", "credit"),
]


def _create_note_tables(prefix: str, parent_fk_table: str, parent_id_column: str) -> None:
    op.create_table(
        f"{prefix}_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(f"{prefix}_note_number", sa.String(length=50), nullable=False),
        sa.Column("vendor_id" if prefix == "debit" else "customer_id", sa.UUID(), nullable=False),
        sa.Column(parent_id_column, sa.UUID(), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("reason", sa.String(length=40), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("applied_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["vendor_id" if prefix == "debit" else "customer_id"],
            ["vendors.id" if prefix == "debit" else "customers.id"],
        ),
        sa.ForeignKeyConstraint([parent_id_column], [parent_fk_table]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(f"{prefix}_note_number", name=f"uq_{prefix}_notes_number"),
    )
    op.create_index(f"ix_{prefix}_notes_status", f"{prefix}_notes", ["status"])

    op.create_table(
        f"{prefix}_note_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(f"{prefix}_note_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint([f"{prefix}_note_id"], [f"{prefix}_notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{prefix}_note_lines_{prefix}_note_id", f"{prefix}_note_lines", [f"{prefix}_note_id"])

    other_id = "invoice_id" if prefix == "credit" else "bill_id"
    other_table = "invoices" if prefix == "credit" else "bills"
    op.create_table(
        f"{prefix}_note_applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(f"{prefix}_note_id", sa.UUID(), nullable=False),
        sa.Column(other_id, sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("applied_on", sa.Date(), nullable=False),
        sa.Column("journal_entry_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint([f"{prefix}_note_id"], [f"{prefix}_notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([other_id], [other_table + ".id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{prefix}_note_applications_{prefix}_note_id", f"{prefix}_note_applications", [f"{prefix}_note_id"])
    op.create_index(f"ix_{prefix}_note_applications_{other_id}", f"{prefix}_note_applications", [other_id])


def upgrade() -> None:
    _create_note_tables("credit", "invoices.id", "original_invoice_id")
    _create_note_tables("debit", "bills.id", "original_bill_id")

    bind = op.get_bind()
    for code, name, account_type, normal_balance in NEW_ACCOUNTS:
        existing = bind.execute(
            sa.text("SELECT 1 FROM accounts WHERE code = :code"), {"code": code}
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
    for prefix in ("debit", "credit"):
        op.drop_table(f"{prefix}_note_applications")
        op.drop_table(f"{prefix}_note_lines")
        op.drop_table(f"{prefix}_notes")
