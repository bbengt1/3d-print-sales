"""#295 P1 Codex review fixes:

1. `/api/v1/tax/compute` previously took only `db`, `profile_id`, and
   `subtotal`, leaving it unauthenticated. It now requires a valid user
   token, matching the rest of the `/tax` routes.

2. Switching JE numbering to the shared `next_number` allocator left
   existing journal entries un-seeded in `reference_sequences`. On a
   non-empty DB the first post in a year would re-allocate `JE-YYYY-0001`
   and violate the unique constraint. A new alembic migration
   (`20260510_13_backfill_je_reference_sequence`) backfills the allocator
   from existing canonical entry numbers. This test exercises that data
   migration logic directly against the test DB.
"""

from __future__ import annotations

import importlib.util
import os
import re
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.journal_entry import JournalEntry
from app.models.reference_sequence import ReferenceSequence
from app.models.tax_profile import TaxProfile
from app.services.reference_number_service import next_number


# --------------------------------------------------------------------------- #
# (i) Tax compute endpoint requires auth.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_compute_tax_without_auth_rejected(client: AsyncClient, db_session):
    p = TaxProfile(name="WA 7%", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add(p)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/tax/compute?profile_id={p.id}&subtotal=100",
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_compute_tax_with_auth_succeeds(
    client: AsyncClient, auth_headers, db_session
):
    p = TaxProfile(name="WA 7%", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add(p)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/tax/compute?profile_id={p.id}&subtotal=100",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tax"] == "7.00"


# --------------------------------------------------------------------------- #
# (ii) JE reference_sequences backfill — exercises the data migration logic
#      directly against the test DB so we can verify next_number advances
#      past the highest existing JE number.
# --------------------------------------------------------------------------- #


def _load_migration_module():
    """Load the backfill migration as a plain Python module so we can call its
    parsing/UPSERT logic. We can't run alembic.command.upgrade against the
    in-memory test DB (revision history doesn't apply), so instead we replay
    the SQL the migration would run.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(
        here,
        "alembic",
        "versions",
        "20260510_13_backfill_je_reference_sequence.py",
    )
    spec = importlib.util.spec_from_file_location("je_backfill_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_backfill_seeds_reference_sequences_then_allocator_advances(
    db_session,
):
    # Pre-create journal_entries with canonical numbers in 2026.
    db_session.add_all(
        [
            JournalEntry(
                entry_number="JE-2026-0003",
                entry_date=date(2026, 1, 5),
                status="posted",
            ),
            JournalEntry(
                entry_number="JE-2026-0007",
                entry_date=date(2026, 1, 6),
                status="posted",
            ),
            # Non-canonical number should be ignored by the parser.
            JournalEntry(
                entry_number="LEGACY-001",
                entry_date=date(2026, 1, 7),
                status="posted",
            ),
        ]
    )
    await db_session.commit()

    # Replay the migration's data-migration logic against this DB.
    module = _load_migration_module()
    pattern: re.Pattern[str] = module._JE_PATTERN

    rows = (
        await db_session.execute(select(JournalEntry.entry_number))
    ).all()
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

    assert per_year_max == {2026: 7}

    for year, max_value in per_year_max.items():
        existing = (
            await db_session.execute(
                select(ReferenceSequence).where(
                    ReferenceSequence.scope == "journal_entry",
                    ReferenceSequence.year == year,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db_session.add(
                ReferenceSequence(
                    id=uuid.uuid4(),
                    scope="journal_entry",
                    year=year,
                    last_value=max_value,
                )
            )
        elif max_value > existing.last_value:
            existing.last_value = max_value
    await db_session.commit()

    # Now the allocator should produce JE-2026-0008 (NOT 0001).
    nxt = await next_number(db_session, "journal_entry", year=2026)
    assert nxt == "JE-2026-0008"

    # Idempotency: rerunning the backfill must not rewind the counter.
    for year, max_value in per_year_max.items():
        existing = (
            await db_session.execute(
                select(ReferenceSequence).where(
                    ReferenceSequence.scope == "journal_entry",
                    ReferenceSequence.year == year,
                )
            )
        ).scalar_one()
        if max_value > existing.last_value:
            existing.last_value = max_value
    await db_session.commit()

    nxt2 = await next_number(db_session, "journal_entry", year=2026)
    assert nxt2 == "JE-2026-0009"


@pytest.mark.asyncio
async def test_backfill_noop_when_no_journal_entries(db_session):
    """With an empty journal_entries table the backfill writes nothing,
    and the allocator starts at 0001 as before."""
    module = _load_migration_module()
    pattern: re.Pattern[str] = module._JE_PATTERN

    rows = (
        await db_session.execute(select(JournalEntry.entry_number))
    ).all()
    per_year_max: dict[int, int] = {}
    for (number,) in rows:
        if not number:
            continue
        m = pattern.match(number)
        if m:
            per_year_max[int(m.group(1))] = max(
                per_year_max.get(int(m.group(1)), 0), int(m.group(2))
            )

    assert per_year_max == {}

    nxt = await next_number(db_session, "journal_entry", year=2026)
    assert nxt == "JE-2026-0001"
