"""Custom-field validation + storage (#253).

Phase 1: values stored in `custom_field_values` (separate table). Each
scope's existing record table is untouched. Trade-off: fetching values
requires a JOIN, but no migration of every record table.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_field import CustomFieldDefinition, CustomFieldValue


class CustomFieldError(RuntimeError):
    pass


VALID_SCOPES = {
    "customer", "vendor", "product", "material", "supply",
    "job", "sale", "invoice", "quote", "bill",
}

FIELD_TYPES = {"text", "long_text", "number", "date", "dropdown", "checkbox"}

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_definition(
    *,
    scope: str,
    key: str,
    field_type: str,
    options: list | None,
) -> None:
    if scope not in VALID_SCOPES:
        raise CustomFieldError(f"Unsupported scope: {scope!r}")
    if not _KEY_RE.match(key):
        raise CustomFieldError(
            "key must start with a lowercase letter and contain only [a-z0-9_]"
        )
    if field_type not in FIELD_TYPES:
        raise CustomFieldError(f"Unknown field_type: {field_type!r}")
    if field_type == "dropdown":
        if not options or not isinstance(options, list) or not all(isinstance(o, str) and o for o in options):
            raise CustomFieldError("dropdown field_type requires non-empty options: list[str]")


def coerce_value(field_type: str, raw: Any, options: list | None) -> str | None:
    """Validate a user-supplied value and return its canonical string form
    for storage. Returns None for empty input."""
    if raw is None or raw == "":
        return None
    if field_type in ("text", "long_text"):
        return str(raw)
    if field_type == "number":
        try:
            return str(Decimal(str(raw)))
        except (InvalidOperation, ValueError) as e:
            raise CustomFieldError(f"Invalid number value: {raw!r}") from e
    if field_type == "date":
        if isinstance(raw, date):
            return raw.isoformat()
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d").date().isoformat()
        except ValueError as e:
            raise CustomFieldError(f"Invalid date value (expected YYYY-MM-DD): {raw!r}") from e
    if field_type == "checkbox":
        if isinstance(raw, bool):
            return "true" if raw else "false"
        s = str(raw).lower()
        if s in ("true", "1", "yes"):
            return "true"
        if s in ("false", "0", "no"):
            return "false"
        raise CustomFieldError(f"Invalid checkbox value: {raw!r}")
    if field_type == "dropdown":
        if not options or str(raw) not in options:
            raise CustomFieldError(f"Value {raw!r} is not in the configured options")
        return str(raw)
    raise CustomFieldError(f"Unhandled field_type: {field_type}")


def decode_value(field_type: str, stored: str | None) -> Any:
    """Reverse of coerce — return native Python representation for the API."""
    if stored is None:
        return None
    if field_type in ("text", "long_text", "dropdown"):
        return stored
    if field_type == "number":
        return str(Decimal(stored))
    if field_type == "date":
        return stored  # ISO string
    if field_type == "checkbox":
        return stored == "true"
    return stored


async def list_definitions(
    db: AsyncSession, *, scope: str, include_inactive: bool = False
) -> list[CustomFieldDefinition]:
    if scope not in VALID_SCOPES:
        raise CustomFieldError(f"Unsupported scope: {scope!r}")
    stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.scope == scope).order_by(
        CustomFieldDefinition.sort_order, CustomFieldDefinition.created_at
    )
    if not include_inactive:
        stmt = stmt.where(CustomFieldDefinition.is_active == True)  # noqa: E712
    return list((await db.execute(stmt)).scalars().all())


async def upsert_values(
    db: AsyncSession,
    *,
    scope: str,
    record_id: uuid.UUID,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Set values for a record. `values` is `{key: raw_value}` for ACTIVE
    definitions only. Required-field check runs across all active defs in
    scope. Returns the canonical decoded values for the record after the
    upsert.
    """
    defs = await list_definitions(db, scope=scope, include_inactive=False)
    by_key = {d.key: d for d in defs}

    # Required-field check
    for d in defs:
        if d.is_required:
            if d.key not in values and not await _has_existing_value(db, d.id, record_id):
                raise CustomFieldError(f"Required custom field missing: {d.key}")

    # Coerce + upsert
    for key, raw in values.items():
        if key not in by_key:
            # Unknown key — silently ignore so client API stays loose
            continue
        d = by_key[key]
        canonical = coerce_value(d.field_type, raw, d.options)
        existing = (
            await db.execute(
                select(CustomFieldValue).where(
                    CustomFieldValue.definition_id == d.id,
                    CustomFieldValue.record_id == record_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                CustomFieldValue(
                    definition_id=d.id,
                    record_id=record_id,
                    value=canonical,
                )
            )
        else:
            existing.value = canonical

    await db.flush()
    return await read_values(db, scope=scope, record_id=record_id)


async def _has_existing_value(db: AsyncSession, definition_id: uuid.UUID, record_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(CustomFieldValue.id).where(
                CustomFieldValue.definition_id == definition_id,
                CustomFieldValue.record_id == record_id,
            )
        )
    ).first()
    return row is not None


async def read_values(
    db: AsyncSession, *, scope: str, record_id: uuid.UUID
) -> dict[str, Any]:
    defs = await list_definitions(db, scope=scope, include_inactive=True)
    by_id = {d.id: d for d in defs}
    rows = (
        await db.execute(
            select(CustomFieldValue).where(
                CustomFieldValue.definition_id.in_(list(by_id.keys())),
                CustomFieldValue.record_id == record_id,
            )
        )
    ).scalars().all()
    return {
        by_id[r.definition_id].key: decode_value(by_id[r.definition_id].field_type, r.value)
        for r in rows
        if r.definition_id in by_id
    }
