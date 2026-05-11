"""#316 P2: bank-rule target FKs for receipt/payment/IAT actions

Revision ID: 20260511_02
Revises: 20260511_01
Create Date: 2026-05-11 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260511_02"
down_revision = "20260511_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("statement_match_rules") as batch:
        batch.add_column(sa.Column("customer_id", sa.UUID(), nullable=True))
        batch.add_column(sa.Column("vendor_id", sa.UUID(), nullable=True))
        batch.add_column(sa.Column("transfer_to_account_id", sa.UUID(), nullable=True))
        batch.create_foreign_key(
            "fk_match_rule_customer", "customers", ["customer_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_match_rule_vendor", "vendors", ["vendor_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_match_rule_transfer_to_account",
            "accounts",
            ["transfer_to_account_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("statement_match_rules") as batch:
        batch.drop_constraint("fk_match_rule_transfer_to_account", type_="foreignkey")
        batch.drop_constraint("fk_match_rule_vendor", type_="foreignkey")
        batch.drop_constraint("fk_match_rule_customer", type_="foreignkey")
        batch.drop_column("transfer_to_account_id")
        batch.drop_column("vendor_id")
        batch.drop_column("customer_id")
