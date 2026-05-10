"""#229: job discovery sources + candidates

Revision ID: 20260510_11
Revises: 20260510_10
Create Date: 2026-05-10 17:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_11"
down_revision = "20260510_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_discovery_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("file_extensions_csv", sa.String(200), nullable=True),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "job_discovery_candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("fingerprint", sa.String(120), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_filename", sa.String(500), nullable=False),
        sa.Column("source_path", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("detected_metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("promoted_job_id", sa.UUID(), nullable=True),
        sa.Column("parse_warnings", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["job_discovery_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promoted_job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "fingerprint", name="uq_candidate_source_fingerprint"),
    )
    op.create_index("ix_job_discovery_candidates_source_id", "job_discovery_candidates", ["source_id"])
    op.create_index("ix_job_discovery_candidates_fingerprint", "job_discovery_candidates", ["fingerprint"])
    op.create_index("ix_job_discovery_candidates_status", "job_discovery_candidates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_job_discovery_candidates_status", table_name="job_discovery_candidates")
    op.drop_index("ix_job_discovery_candidates_fingerprint", table_name="job_discovery_candidates")
    op.drop_index("ix_job_discovery_candidates_source_id", table_name="job_discovery_candidates")
    op.drop_table("job_discovery_candidates")
    op.drop_table("job_discovery_sources")
