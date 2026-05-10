"""#328 P2: division/project FKs across docs

Revision ID: 20260510_05
Revises: 20260510_04
Create Date: 2026-05-10 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_05"
down_revision = "20260510_04"
branch_labels = None
depends_on = None


TABLES = ("invoices", "bills", "sales", "journal_entries", "quotes", "expense_claims")


def upgrade() -> None:
    for tbl in TABLES:
        with op.batch_alter_table(tbl) as batch:
            batch.add_column(sa.Column("division_id", sa.UUID(), nullable=True))
            batch.add_column(sa.Column("project_id", sa.UUID(), nullable=True))
            batch.create_foreign_key(
                f"fk_{tbl}_division", "divisions", ["division_id"], ["id"]
            )
            batch.create_foreign_key(
                f"fk_{tbl}_project", "projects", ["project_id"], ["id"]
            )
        op.create_index(f"ix_{tbl}_division_id", tbl, ["division_id"])
        op.create_index(f"ix_{tbl}_project_id", tbl, ["project_id"])


def downgrade() -> None:
    for tbl in TABLES:
        op.drop_index(f"ix_{tbl}_project_id", table_name=tbl)
        op.drop_index(f"ix_{tbl}_division_id", table_name=tbl)
        with op.batch_alter_table(tbl) as batch:
            batch.drop_constraint(f"fk_{tbl}_project", type_="foreignkey")
            batch.drop_constraint(f"fk_{tbl}_division", type_="foreignkey")
            batch.drop_column("project_id")
            batch.drop_column("division_id")
