from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DB, CurrentAdmin
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/logs", response_model=list[AuditLogResponse], summary="List audit logs (admin only)")
async def list_audit_logs(
    admin: CurrentAdmin,
    db: DB,
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    result = await db.execute(stmt)
    return result.scalars().all()
