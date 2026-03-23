"""add sales tax tracking

Revision ID: 20260323_04
Revises: 20260323_03
Create Date: 2026-03-23 07:35:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260323_04"
down_revision: Union[str, None] = "20260323_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tax_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("tax_rate", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("filing_frequency", sa.String(length=20), nullable=True),
        sa.Column("is_marketplace_facilitated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_profiles_name"), "tax_profiles", ["name"], unique=True)

    op.create_table(
        "tax_remittances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tax_profile_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("remittance_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_number", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tax_profile_id"], ["tax_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_remittances_tax_profile_id"), "tax_remittances", ["tax_profile_id"], unique=False)

    op.add_column("sales", sa.Column("tax_profile_id", sa.UUID(), nullable=True))
    op.add_column("sales", sa.Column("tax_treatment", sa.String(length=30), nullable=False, server_default="seller_collected"))
    op.create_foreign_key("fk_sales_tax_profile_id", "sales", "tax_profiles", ["tax_profile_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_sales_tax_profile_id", "sales", type_="foreignkey")
    op.drop_column("sales", "tax_treatment")
    op.drop_column("sales", "tax_profile_id")
    op.drop_index(op.f("ix_tax_remittances_tax_profile_id"), table_name="tax_remittances")
    op.drop_table("tax_remittances")
    op.drop_index(op.f("ix_tax_profiles_name"), table_name="tax_profiles")
    op.drop_table("tax_profiles")
