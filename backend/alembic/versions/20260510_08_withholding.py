"""#263 P2: withholding_profiles + customer.withholding_profile_id

Revision ID: 20260510_08
Revises: 20260510_07
Create Date: 2026-05-10 14:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_08"
down_revision = "20260510_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "withholding_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("rate_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("liability_account_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["liability_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("withholding_profile_id", sa.UUID(), nullable=True))
        batch.create_foreign_key(
            "fk_customers_withholding_profile",
            "withholding_profiles",
            ["withholding_profile_id"],
            ["id"],
        )
    op.create_index("ix_customers_withholding_profile_id", "customers", ["withholding_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_customers_withholding_profile_id", table_name="customers")
    with op.batch_alter_table("customers") as batch:
        batch.drop_constraint("fk_customers_withholding_profile", type_="foreignkey")
        batch.drop_column("withholding_profile_id")
    op.drop_table("withholding_profiles")
