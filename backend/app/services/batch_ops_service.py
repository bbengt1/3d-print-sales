"""Batch operations on master-data scopes (#254 Phase 1).

Phase 1 supports batch deactivate / activate / hard-delete across the
listed master-data tables. Each row is processed independently; errors
are returned per-row so partial-success is visible. Transactions are
deliberately excluded — they have ledger side-effects and are too
risky for bulk modification.

CSV import is deferred to Phase 2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.material import Material
from app.models.product import Product
from app.models.supply import Supply
from app.models.vendor import Vendor


class BatchOpsError(RuntimeError):
    pass


@dataclass
class _ScopeConfig:
    model: type
    active_field: str | None  # None means "no soft-deactivate available"


SCOPES: dict[str, _ScopeConfig] = {
    "customer": _ScopeConfig(model=Customer, active_field=None),
    "vendor": _ScopeConfig(model=Vendor, active_field="is_active"),
    "product": _ScopeConfig(model=Product, active_field="is_active"),
    "material": _ScopeConfig(model=Material, active_field=None),
    "supply": _ScopeConfig(model=Supply, active_field="active"),
}


def _config(scope: str) -> _ScopeConfig:
    if scope not in SCOPES:
        raise BatchOpsError(f"Unsupported scope: {scope!r}")
    return SCOPES[scope]


async def _set_active(
    db: AsyncSession,
    *,
    scope: str,
    ids: list[uuid.UUID],
    active: bool,
) -> dict:
    cfg = _config(scope)
    if cfg.active_field is None:
        raise BatchOpsError(
            f"Scope {scope!r} has no soft-deactivate field — use delete"
        )
    if not ids:
        return {"updated": 0, "errors": []}

    rows = (await db.execute(select(cfg.model).where(cfg.model.id.in_(ids)))).scalars().all()
    by_id = {r.id: r for r in rows}
    updated = 0
    errors = []
    for rid in ids:
        if rid not in by_id:
            errors.append({"id": str(rid), "error": "not found"})
            continue
        setattr(by_id[rid], cfg.active_field, active)
        updated += 1
    await db.flush()
    return {"updated": updated, "errors": errors}


async def batch_deactivate(db: AsyncSession, *, scope: str, ids: list[uuid.UUID]) -> dict:
    return await _set_active(db, scope=scope, ids=ids, active=False)


async def batch_activate(db: AsyncSession, *, scope: str, ids: list[uuid.UUID]) -> dict:
    return await _set_active(db, scope=scope, ids=ids, active=True)


async def batch_delete(db: AsyncSession, *, scope: str, ids: list[uuid.UUID]) -> dict:
    """Hard delete. Each row attempted independently; FK constraint
    violations are caught per-row so partial success is reported.
    """
    cfg = _config(scope)
    if not ids:
        return {"deleted": 0, "errors": []}

    deleted = 0
    errors = []
    for rid in ids:
        row = (await db.execute(select(cfg.model).where(cfg.model.id == rid))).scalar_one_or_none()
        if row is None:
            errors.append({"id": str(rid), "error": "not found"})
            continue
        try:
            await db.delete(row)
            await db.flush()
            deleted += 1
        except IntegrityError as e:
            await db.rollback()
            errors.append({"id": str(rid), "error": f"foreign-key dependency: {e.orig}"})
    return {"deleted": deleted, "errors": errors}
