"""#316 P2: extend statement_match_rules with category_account_id + counterparty

Revision ID: 20260510_01
Revises: 20260509_22
Create Date: 2026-05-10 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_01"
down_revision = "20260509_22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("statement_match_rules") as batch:
        batch.add_column(sa.Column("category_account_id", sa.UUID(), nullable=True))
        batch.add_column(sa.Column("counterparty_name", sa.String(200), nullable=True))
        batch.create_foreign_key(
            "fk_match_rule_category_account",
            "accounts",
            ["category_account_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("statement_match_rules") as batch:
        batch.drop_constraint("fk_match_rule_category_account", type_="foreignkey")
        batch.drop_column("counterparty_name")
        batch.drop_column("category_account_id")
