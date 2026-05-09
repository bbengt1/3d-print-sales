"""add intangible_assets, amortization_entries, and IA-related COA seed (#252)

Revision ID: 20260509_10
Revises: 20260509_09
Create Date: 2026-05-09 23:45:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_10"
down_revision = "20260509_09"
branch_labels = None
depends_on = None


NEW_ACCOUNTS = [
    ("1800", "Intangible Assets", "asset", "debit"),
    ("1850", "Accumulated Amortization", "asset", "credit"),
    ("6750", "Amortization Expense", "expense", "debit"),
    ("4920", "Gain on Disposal of Intangibles", "revenue", "credit"),
    ("6760", "Loss on Disposal of Intangibles", "expense", "debit"),
]


def upgrade() -> None:
    op.create_table(
        "intangible_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("asset_tag", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acquired_on", sa.Date(), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("salvage_value", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("amortization_method", sa.String(length=30), nullable=False, server_default="straight_line"),
        sa.Column("declining_balance_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("asset_account_id", sa.UUID(), nullable=False),
        sa.Column("accumulated_amortization_account_id", sa.UUID(), nullable=False),
        sa.Column("amortization_expense_account_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("disposed_on", sa.Date(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(14, 4), nullable=True),
        sa.Column("disposal_journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["accumulated_amortization_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["amortization_expense_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["disposal_journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_tag", name="uq_intangible_assets_asset_tag"),
    )
    op.create_index("ix_intangible_assets_name", "intangible_assets", ["name"])
    op.create_index("ix_intangible_assets_status", "intangible_assets", ["status"])

    op.create_table(
        "amortization_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("intangible_asset_id", sa.UUID(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("journal_entry_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["intangible_asset_id"], ["intangible_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "intangible_asset_id", "period_end",
            name="uq_amortization_entries_asset_period",
        ),
    )
    op.create_index(
        "ix_amortization_entries_intangible_asset_id",
        "amortization_entries",
        ["intangible_asset_id"],
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
    op.drop_index("ix_amortization_entries_intangible_asset_id", table_name="amortization_entries")
    op.drop_table("amortization_entries")
    op.drop_index("ix_intangible_assets_status", table_name="intangible_assets")
    op.drop_index("ix_intangible_assets_name", table_name="intangible_assets")
    op.drop_table("intangible_assets")
