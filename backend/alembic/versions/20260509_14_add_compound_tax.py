"""compound + reverse-charge tax: tax_profile_components + new flags (#258)

Revision ID: 20260509_14
Revises: 20260509_13
Create Date: 2026-05-10 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_14"
down_revision = "20260509_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_profiles",
        sa.Column("is_compound", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tax_profiles",
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tax_profiles",
        sa.Column("receivable_account_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tax_profiles_receivable_account_id",
        "tax_profiles",
        "accounts",
        ["receivable_account_id"],
        ["id"],
    )

    op.create_table(
        "tax_profile_components",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("apply_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("liability_account_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["tax_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["liability_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tax_profile_components_profile_id", "tax_profile_components", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_tax_profile_components_profile_id", table_name="tax_profile_components")
    op.drop_table("tax_profile_components")
    op.drop_constraint("fk_tax_profiles_receivable_account_id", "tax_profiles", type_="foreignkey")
    op.drop_column("tax_profiles", "receivable_account_id")
    op.drop_column("tax_profiles", "is_reverse_charge")
    op.drop_column("tax_profiles", "is_compound")
