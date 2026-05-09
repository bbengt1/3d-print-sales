"""add reference_sequences allocator + backfill from existing canonical numbers

Revision ID: 20260509_01
Revises: 20260508_03
Create Date: 2026-05-09 16:00:00
"""

from __future__ import annotations

import re
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260509_01"
down_revision = "20260508_03"
branch_labels = None
depends_on = None


CANONICAL_PATTERNS = {
    "sale": (re.compile(r"^S-(\d{4})-(\d+)$"), "sales", "sale_number"),
    "invoice": (re.compile(r"^INV-(\d{4})-(\d+)$"), "invoices", "invoice_number"),
    "quote": (re.compile(r"^Q-(\d{4})-(\d+)$"), "quotes", "quote_number"),
}


def upgrade() -> None:
    op.create_table(
        "reference_sequences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "year", name="uq_reference_sequences_scope_year"),
    )
    op.create_index("ix_reference_sequences_scope", "reference_sequences", ["scope"])
    op.create_index("ix_reference_sequences_year", "reference_sequences", ["year"])

    # Backfill: for each canonical scope, parse existing numbers and seed
    # `last_value = max(parsed numeric suffix)` per (scope, year). Records that
    # don't match the canonical pattern (operator-supplied invoice numbers
    # like "CUST-PROJECT-7") simply don't influence the seed; they continue
    # to coexist on the parent table without affecting the allocator.
    bind = op.get_bind()
    for scope, (pattern, table, column) in CANONICAL_PATTERNS.items():
        try:
            rows = bind.execute(sa.text(f"SELECT {column} FROM {table}")).all()
        except Exception:
            continue
        per_year_max: dict[int, int] = {}
        for (number,) in rows:
            if not number:
                continue
            m = pattern.match(number)
            if not m:
                continue
            year = int(m.group(1))
            value = int(m.group(2))
            per_year_max[year] = max(per_year_max.get(year, 0), value)
        for year, max_value in per_year_max.items():
            bind.execute(
                sa.text(
                    "INSERT INTO reference_sequences (id, scope, year, last_value) "
                    "VALUES (:id, :scope, :year, :last_value)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "scope": scope,
                    "year": year,
                    "last_value": max_value,
                },
            )


def downgrade() -> None:
    op.drop_index("ix_reference_sequences_year", table_name="reference_sequences")
    op.drop_index("ix_reference_sequences_scope", table_name="reference_sequences")
    op.drop_table("reference_sequences")
