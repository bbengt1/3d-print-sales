from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.services.batch_ops_service import (
    BatchOpsError,
    SCOPES,
    batch_activate,
    batch_deactivate,
    batch_delete,
)


router = APIRouter(prefix="/batch", tags=["BatchOperations"])


class BatchRequest(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)


@router.post("/{scope}/deactivate", summary="Batch-deactivate master records (soft)")
async def deactivate_ep(scope: str, body: BatchRequest, user: CurrentUser, db: DB):
    try:
        result = await batch_deactivate(db, scope=scope, ids=body.ids)
    except BatchOpsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result


@router.post("/{scope}/activate", summary="Batch-reactivate master records")
async def activate_ep(scope: str, body: BatchRequest, user: CurrentUser, db: DB):
    try:
        result = await batch_activate(db, scope=scope, ids=body.ids)
    except BatchOpsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result


@router.post("/{scope}/delete", summary="Batch hard-delete (per-row error reporting on FK violations)")
async def delete_ep(scope: str, body: BatchRequest, user: CurrentUser, db: DB):
    try:
        result = await batch_delete(db, scope=scope, ids=body.ids)
    except BatchOpsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result


@router.get("/scopes", summary="List supported batch-op scopes and their soft-deactivate availability")
async def list_scopes(user: CurrentUser, db: DB):
    return {
        s: {"deactivatable": cfg.active_field is not None}
        for s, cfg in SCOPES.items()
    }
