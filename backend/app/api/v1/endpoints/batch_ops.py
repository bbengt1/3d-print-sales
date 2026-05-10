from __future__ import annotations

import uuid
from typing import Literal

import csv
import io

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.services.batch_ops_service import (
    BatchOpsError,
    CSV_IMPORT_FIELDS,
    SCOPES,
    batch_activate,
    batch_deactivate,
    batch_delete,
    import_master_csv,
    undo_csv_batch,
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


@router.post(
    "/{scope}/import.csv",
    summary="#327 P2: Bulk-create master records from a CSV; returns batch_id for undo",
)
async def import_csv(
    scope: str,
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
):
    if scope not in CSV_IMPORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"CSV import not configured for scope {scope!r}; supported: {sorted(CSV_IMPORT_FIELDS)}",
        )
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    fields = CSV_IMPORT_FIELDS[scope]
    if not reader.fieldnames or fields[0] not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail=f"CSV must include `{fields[0]}` column (and optionally: {fields[1:]})",
        )
    rows = list(reader)
    try:
        result = await import_master_csv(
            db, scope=scope, rows=rows, actor_user_id=user.id
        )
    except BatchOpsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result


@router.post(
    "/sessions/{batch_id}/undo",
    summary="#327 P2: Undo a CSV import batch — hard-deletes the records it created",
)
async def undo_batch(batch_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        result = await undo_csv_batch(db, batch_id=batch_id, actor_user_id=user.id)
    except BatchOpsError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await db.commit()
    return result
