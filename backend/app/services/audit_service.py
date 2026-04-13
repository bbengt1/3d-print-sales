from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.models.audit_log import AuditLog


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


def snapshot_model(obj, fields: list[str]) -> dict:
    return {field: _json_safe(getattr(obj, field, None)) for field in fields}


async def create_audit_log(db, *, actor_user_id=None, entity_type: str, entity_id: str, action: str, before_snapshot=None, after_snapshot=None, reason: str | None = None):
    event = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        reason=reason,
        before_snapshot=_json_safe(before_snapshot),
        after_snapshot=_json_safe(after_snapshot),
    )
    db.add(event)
    await db.flush()
    return event
