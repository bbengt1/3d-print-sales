from __future__ import annotations

import re
from datetime import date
from typing import Final

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference_sequence import ReferenceSequence


# Per-scope format strings. Each must accept `year` (int) and `value` (int).
# When adding a new scope (e.g. inventory_transfer, production_order), register
# its format here and that's all that's needed for the allocator to support it.
FORMATS: Final[dict[str, str]] = {
    "sale": "S-{year}-{value:04d}",
    "invoice": "INV-{year}-{value:04d}",
    "quote": "Q-{year}-{value:04d}",
    "inventory_transfer": "IT-{year}-{value:04d}",
    "inter_account_transfer": "T-{year}-{value:04d}",
}


# Compiled regex per scope used by the migration backfill to parse existing
# canonical-format numbers into a numeric suffix. Scopes with non-canonical
# numbers (e.g. operator-supplied invoice numbers like "CUST-PROJECT-7") simply
# don't match these and are ignored during seeding.
_PARSE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "sale": re.compile(r"^S-(\d{4})-(\d+)$"),
    "invoice": re.compile(r"^INV-(\d{4})-(\d+)$"),
    "quote": re.compile(r"^Q-(\d{4})-(\d+)$"),
}


def parse_reference_number(scope: str, number: str) -> tuple[int, int] | None:
    """Parse a canonical reference number for `scope` into (year, value).

    Returns None when the input doesn't match the canonical pattern; backfill
    callers use this to skip non-canonical historical numbers.
    """
    pattern = _PARSE_PATTERNS.get(scope)
    if pattern is None:
        return None
    m = pattern.match(number)
    if m is None:
        return None
    return int(m.group(1)), int(m.group(2))


def format_reference_number(scope: str, year: int, value: int) -> str:
    if scope not in FORMATS:
        raise KeyError(f"Unknown reference number scope: {scope!r}")
    return FORMATS[scope].format(year=year, value=value)


async def next_number(
    session: AsyncSession,
    scope: str,
    year: int | None = None,
) -> str:
    """Atomically allocate and format the next reference number for (scope, year).

    Caller must invoke this inside the same transaction that inserts the parent
    record. Rollback of the outer transaction rolls back the increment, which
    intentionally causes the next call to reissue the same number — accountants
    consider that a feature, not a bug, because it keeps numbers contiguous on
    successful posts. If a row creation fails after this call, the burned
    number is acceptable per #243's design (skipped numbers OK).

    On PostgreSQL the increment is one statement (`INSERT ... ON CONFLICT
    DO UPDATE ... RETURNING`). On SQLite (test path) we fall back to
    select-then-update, which is single-threaded enough to be safe.
    """
    if scope not in FORMATS:
        raise KeyError(f"Unknown reference number scope: {scope!r}")

    if year is None:
        year = date.today().year

    dialect = session.bind.dialect.name if session.bind else "postgresql"

    if dialect == "postgresql":
        stmt = pg_insert(ReferenceSequence).values(
            scope=scope, year=year, last_value=1
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["scope", "year"],
            set_={"last_value": ReferenceSequence.last_value + 1},
        ).returning(ReferenceSequence.last_value)
        result = await session.execute(stmt)
        new_value = result.scalar_one()
    else:
        # SQLite test path. Tests run serially so no real race; this just needs
        # to be correct.
        existing = await session.execute(
            select(ReferenceSequence).where(
                ReferenceSequence.scope == scope,
                ReferenceSequence.year == year,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = ReferenceSequence(scope=scope, year=year, last_value=1)
            session.add(row)
            await session.flush()
            new_value = 1
        else:
            new_value = row.last_value + 1
            await session.execute(
                update(ReferenceSequence)
                .where(ReferenceSequence.id == row.id)
                .values(last_value=new_value)
            )

    return format_reference_number(scope, year, new_value)


async def seed_sequence(
    session: AsyncSession,
    *,
    scope: str,
    year: int,
    last_value: int,
) -> None:
    """Idempotent seed used by migrations. If the (scope, year) row exists,
    leave it alone. Otherwise insert with the given last_value.
    """
    existing = await session.execute(
        select(ReferenceSequence).where(
            ReferenceSequence.scope == scope,
            ReferenceSequence.year == year,
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(
            ReferenceSequence(scope=scope, year=year, last_value=last_value)
        )
        await session.flush()
