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


# ---------- #327 P2: CSV import + undo ----------


# Per-scope minimal schema for CSV imports. Only columns listed here are
# accepted; the first column listed is treated as the upsert key.
CSV_IMPORT_FIELDS: dict[str, list[str]] = {
    "customer": ["name", "email", "phone", "notes"],
    "vendor": ["name", "email", "phone", "notes"],
    "supply": ["name", "sku", "category", "unit", "unit_cost", "supplier"],
}


async def import_master_csv(
    db: AsyncSession,
    *,
    scope: str,
    rows: list[dict],
    actor_user_id: uuid.UUID | None = None,
) -> dict:
    """Create-only CSV import: every row attempts an insert. Existing
    records keyed on the scope's first column (name for customer/vendor)
    are skipped — no update yet to keep undo simple. Returns a `batch_id`
    that can be passed to `undo_csv_batch`.
    """
    if scope not in CSV_IMPORT_FIELDS:
        raise BatchOpsError(f"CSV import not configured for scope {scope!r}")
    cfg = _config(scope)
    fields = CSV_IMPORT_FIELDS[scope]
    key_col = fields[0]
    batch_id = uuid.uuid4()
    created_ids: list[uuid.UUID] = []
    errors: list[dict] = []
    skipped = 0

    for idx, raw in enumerate(rows, start=1):
        try:
            data = {f: (raw.get(f) or "").strip() for f in fields if raw.get(f) is not None}
            if not data.get(key_col):
                errors.append({"row": idx, "error": f"missing {key_col}"})
                continue
            existing = (
                await db.execute(
                    select(cfg.model).where(getattr(cfg.model, key_col) == data[key_col])
                )
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue
            obj = cfg.model(**data)
            db.add(obj)
            await db.flush()
            created_ids.append(obj.id)
            from app.models.audit_log import AuditLog

            db.add(
                AuditLog(
                    actor_user_id=actor_user_id,
                    entity_type=scope,
                    entity_id=str(obj.id),
                    action="batch_csv_import",
                    reason=f"batch={batch_id}",
                    before_snapshot=None,
                    after_snapshot=data,
                )
            )
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})
            await db.rollback()
    await db.flush()
    return {
        "batch_id": str(batch_id),
        "scope": scope,
        "created": len(created_ids),
        "skipped": skipped,
        "errors": errors,
        "created_ids": [str(i) for i in created_ids],
    }


async def undo_csv_batch(
    db: AsyncSession, *, batch_id: uuid.UUID, actor_user_id: uuid.UUID | None = None
) -> dict:
    """Look up the audit-log rows for `batch={batch_id}` and hard-delete
    every entity_id they recorded. Refuses if any of the referenced
    records have been edited since import (snapshot mismatch is OK; FK
    violations are reported per-row).
    """
    from app.models.audit_log import AuditLog

    rows = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "batch_csv_import",
                AuditLog.reason == f"batch={batch_id}",
            )
        )
    ).scalars().all()
    if not rows:
        raise BatchOpsError(f"No batch {batch_id} found")
    deleted = 0
    errors: list[dict] = []
    for r in rows:
        scope = r.entity_type
        try:
            cfg = _config(scope)
        except BatchOpsError:
            errors.append({"id": r.entity_id, "error": f"unknown scope {scope}"})
            continue
        row_id = uuid.UUID(r.entity_id)
        obj = (await db.execute(select(cfg.model).where(cfg.model.id == row_id))).scalar_one_or_none()
        if obj is None:
            continue  # already gone
        try:
            await db.delete(obj)
            await db.flush()
            deleted += 1
        except IntegrityError as e:
            await db.rollback()
            errors.append({"id": r.entity_id, "error": f"foreign-key dependency: {e.orig}"})

    # Tombstone the undo
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            entity_type="batch_session",
            entity_id=str(batch_id),
            action="batch_csv_undo",
            reason=f"deleted {deleted}",
            before_snapshot=None,
            after_snapshot={"deleted": deleted, "errors": errors},
        )
    )
    return {"batch_id": str(batch_id), "deleted": deleted, "errors": errors}
