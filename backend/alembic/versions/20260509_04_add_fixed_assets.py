"""add fixed_assets, depreciation_entries, and printers.fixed_asset_id

Revision ID: 20260509_04
Revises: 20260509_03
Create Date: 2026-05-09 19:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_04"
down_revision = "20260509_03"
branch_labels = None
depends_on = None


# Mirrors the new FA-related accounts added to STARTER_CHART_OF_ACCOUNTS.
# We re-seed here so existing installations get them without depending on
# the seeder running from the lifespan path.
NEW_ACCOUNTS = [
    ("1700", "Equipment", "asset", "debit"),
    ("1750", "Accumulated Depreciation — Equipment", "asset", "credit"),
    ("6700", "Depreciation Expense", "expense", "debit"),
    ("4910", "Gain on Disposal of Equipment", "revenue", "credit"),
    ("6710", "Loss on Disposal of Equipment", "expense", "debit"),
]


def upgrade() -> None:
    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("asset_tag", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acquired_on", sa.Date(), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("salvage_value", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", sa.String(length=30), nullable=False, server_default="straight_line"),
        sa.Column("declining_balance_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("asset_account_id", sa.UUID(), nullable=False),
        sa.Column("accumulated_depreciation_account_id", sa.UUID(), nullable=False),
        sa.Column("depreciation_expense_account_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("disposed_on", sa.Date(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(14, 4), nullable=True),
        sa.Column("disposal_journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("acquisition_bill_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["accumulated_depreciation_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["depreciation_expense_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["disposal_journal_entry_id"], ["journal_entries.id"]),
        sa.ForeignKeyConstraint(["acquisition_bill_id"], ["bills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_tag", name="uq_fixed_assets_asset_tag"),
    )
    op.create_index("ix_fixed_assets_name", "fixed_assets", ["name"])
    op.create_index("ix_fixed_assets_status", "fixed_assets", ["status"])

    op.create_table(
        "depreciation_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fixed_asset_id", sa.UUID(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("journal_entry_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["fixed_asset_id"], ["fixed_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fixed_asset_id", "period_end",
            name="uq_depreciation_entries_asset_period",
        ),
    )
    op.create_index("ix_depreciation_entries_fixed_asset_id", "depreciation_entries", ["fixed_asset_id"])
    op.create_index("ix_depreciation_entries_period_end", "depreciation_entries", ["period_end"])

    op.add_column(
        "printers",
        sa.Column("fixed_asset_id", sa.UUID(), nullable=True),
    )
    op.create_index("ix_printers_fixed_asset_id", "printers", ["fixed_asset_id"])
    op.create_foreign_key(
        "fk_printers_fixed_asset_id",
        "printers",
        "fixed_assets",
        ["fixed_asset_id"],
        ["id"],
    )

    # Idempotent seed of the new chart-of-accounts entries (mirror of
    # `STARTER_CHART_OF_ACCOUNTS` additions in #238).
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
    op.drop_constraint("fk_printers_fixed_asset_id", "printers", type_="foreignkey")
    op.drop_index("ix_printers_fixed_asset_id", table_name="printers")
    op.drop_column("printers", "fixed_asset_id")

    op.drop_index("ix_depreciation_entries_period_end", table_name="depreciation_entries")
    op.drop_index("ix_depreciation_entries_fixed_asset_id", table_name="depreciation_entries")
    op.drop_table("depreciation_entries")

    op.drop_index("ix_fixed_assets_status", table_name="fixed_assets")
    op.drop_index("ix_fixed_assets_name", table_name="fixed_assets")
    op.drop_table("fixed_assets")
