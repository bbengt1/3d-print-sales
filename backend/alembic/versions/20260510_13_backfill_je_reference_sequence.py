"""#295 P1: backfill reference_sequences from existing journal_entries

The accounting service was switched to use the shared `next_number` allocator
for JE numbering (`scope='journal_entry'`), but no migration seeded
`reference_sequences` from existing journal entries. On any non-empty
database, the first post in a year would re-allocate `JE-YYYY-0001` and
violate the unique `journal_entries.entry_number` constraint, blocking new
journal-entry creation after upgrade.

This migration parses existing canonical `JE-YYYY-NNNN` numbers, computes
`max(NNNN)` per year, and UPSERTs into `reference_sequences`. It is
idempotent: re-running raises `last_value` only if the parsed max is
strictly greater than the stored one.

Revision ID: 20260510_13
Revises: 20260510_12
Create Date: 2026-05-10 19:00:00
"""

from __future__ import annotations

import re
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260510_13"
down_revision = "20260510_12"
branch_labels = None
depends_on = None


_JE_PATTERN = re.compile(r"^JE-(\d{4})-(\d+)$")


def upgrade() -> None:
    bind = op.get_bind()
    try:
        rows = bind.execute(
            sa.text("SELECT entry_number FROM journal_entries")
        ).all()
    except Exception:
        # journal_entries table doesn't exist yet (fresh install). Nothing to do.
        return

    per_year_max: dict[int, int] = {}
    for (number,) in rows:
        if not number:
            continue
        m = _JE_PATTERN.match(number)
        if not m:
            continue
        year = int(m.group(1))
        value = int(m.group(2))
        per_year_max[year] = max(per_year_max.get(year, 0), value)

    for year, max_value in per_year_max.items():
        # Idempotent UPSERT: insert when missing; otherwise raise last_value
        # only if our parsed max is strictly greater than what's already there
        # (e.g. a re-run after the allocator has already advanced should not
        # rewind the counter).
        existing = bind.execute(
            sa.text(
                "SELECT id, last_value FROM reference_sequences "
                "WHERE scope = :scope AND year = :year"
            ),
            {"scope": "journal_entry", "year": year},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO reference_sequences (id, scope, year, last_value) "
                    "VALUES (:id, :scope, :year, :last_value)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "scope": "journal_entry",
                    "year": year,
                    "last_value": max_value,
                },
            )
        else:
            current = int(existing[1])
            if max_value > current:
                bind.execute(
                    sa.text(
                        "UPDATE reference_sequences SET last_value = :last_value "
                        "WHERE scope = :scope AND year = :year"
                    ),
                    {
                        "scope": "journal_entry",
                        "year": year,
                        "last_value": max_value,
                    },
                )


def downgrade() -> None:
    # Data-only migration; remove the journal_entry seeds we created.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM reference_sequences WHERE scope = :scope"
        ),
        {"scope": "journal_entry"},
    )
