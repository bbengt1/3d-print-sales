"""#328 P2 follow-up: Job → Project FK

Closes the last remaining bullet on #328 (Job rollup into Project) — the
P&L by project filter already accepts project_id on doc rows, but Job
itself had no link until now.

Revision ID: 20260511_06
Revises: 20260511_05
Create Date: 2026-05-11 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260511_06"
down_revision = "20260511_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("project_id", sa.UUID(), nullable=True))
        batch.create_foreign_key(
            "fk_jobs_project", "projects", ["project_id"], ["id"]
        )
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_project_id", table_name="jobs")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("fk_jobs_project", type_="foreignkey")
        batch.drop_column("project_id")
