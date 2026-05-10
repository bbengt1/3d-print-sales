"""#230: catalog loaded filament from prints.

`resolve_or_catalog` takes filament metadata reported by a print job /
slicer / printer telemetry, looks it up in the existing `materials`
table, and either:

- returns an existing match (`created=False`)
- creates a new Material with `discovered_via` populated (`created=True`)
- creates a Material flagged `needs_review=True` when source data is
  ambiguous (`created=True, needs_review=True`)

Matching keys, in order of preference:
  1. exact case-insensitive (brand, name)
  2. case-insensitive name only (when the source has no brand)
  3. spool_id from `discovery_metadata` of an existing record (lets a
     printer's spool ID stay sticky even if the operator renames the
     material)

The cost defaults are intentionally conservative: when source data
doesn't carry pricing, the new Material is flagged `needs_review` so the
operator can fix it before it pollutes COGS calculations.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material


SUPPORTED_SOURCES = {
    "print_job",
    "slicer_metadata",
    "printer_telemetry",
    "csv_import",
    "opening_balance",
}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


async def _match_by_brand_and_name(
    db: AsyncSession, brand: str | None, name: str
) -> Material | None:
    if brand:
        row = (
            await db.execute(
                select(Material).where(
                    func.lower(Material.brand) == _norm(brand),
                    func.lower(Material.name) == _norm(name),
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
    # Name-only fallback (when the source has no brand)
    row = (
        await db.execute(
            select(Material).where(func.lower(Material.name) == _norm(name)).limit(2)
        )
    ).scalars().all()
    if len(row) == 1:
        return row[0]
    return None


async def _match_by_spool_id(
    db: AsyncSession, spool_id: str | None
) -> Material | None:
    if not spool_id:
        return None
    # Brute-force match: scan materials with non-null discovery_metadata
    # and look for spool_id key. SQLite doesn't support JSON path filters
    # uniformly across versions; this small scan is fine for catalog sizes
    # we expect (hundreds, not millions).
    rows = (
        await db.execute(select(Material).where(Material.discovery_metadata.is_not(None)))
    ).scalars().all()
    for r in rows:
        meta = r.discovery_metadata or {}
        if meta.get("spool_id") and str(meta["spool_id"]) == str(spool_id):
            return r
    return None


def _has_pricing(spool_weight_g, spool_price, net_usable_g, cost_per_g) -> bool:
    return (
        spool_weight_g is not None
        and spool_price is not None
        and net_usable_g is not None
        and cost_per_g is not None
    )


async def resolve_or_catalog(
    db: AsyncSession,
    *,
    name: str,
    brand: str | None = None,
    color: str | None = None,
    spool_id: str | None = None,
    source: str,
    source_printer_id: str | None = None,
    source_job_id: str | None = None,
    spool_weight_g: Decimal | None = None,
    spool_price: Decimal | None = None,
    net_usable_g: Decimal | None = None,
    cost_per_g: Decimal | None = None,
) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("name is required")
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unknown source {source!r}; expected one of {sorted(SUPPORTED_SOURCES)}")

    # Try matching strategies in order
    match = await _match_by_spool_id(db, spool_id)
    matched_via = "spool_id" if match else None
    if match is None:
        match = await _match_by_brand_and_name(db, brand, name)
        if match is not None:
            matched_via = "brand_and_name" if brand else "name_only"

    if match is not None:
        return {
            "material_id": str(match.id),
            "name": match.name,
            "brand": match.brand,
            "created": False,
            "needs_review": match.needs_review,
            "matched_via": matched_via,
        }

    # Build a new Material from whatever the source gave us. If pricing is
    # missing, mark needs_review and use safe placeholders so DB constraints
    # are satisfied without polluting COGS reports.
    metadata = {
        "source": source,
        "discovered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "color": color,
        "spool_id": spool_id,
        "printer_id": source_printer_id,
        "job_id": source_job_id,
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    needs_review = not _has_pricing(spool_weight_g, spool_price, net_usable_g, cost_per_g)
    new_mat = Material(
        name=name.strip(),
        brand=(brand or "Unknown").strip(),
        spool_weight_g=Decimal(spool_weight_g) if spool_weight_g is not None else Decimal("1000"),
        spool_price=Decimal(spool_price) if spool_price is not None else Decimal("0"),
        net_usable_g=Decimal(net_usable_g) if net_usable_g is not None else Decimal("0"),
        cost_per_g=Decimal(cost_per_g) if cost_per_g is not None else Decimal("0"),
        notes=("Auto-cataloged — needs review" if needs_review else None),
        discovered_via=source,
        discovery_metadata=metadata,
        needs_review=needs_review,
    )
    db.add(new_mat)
    await db.flush()
    return {
        "material_id": str(new_mat.id),
        "name": new_mat.name,
        "brand": new_mat.brand,
        "created": True,
        "needs_review": needs_review,
        "matched_via": None,
    }
