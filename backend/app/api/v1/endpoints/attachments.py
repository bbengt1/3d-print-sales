from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.attachment import Attachment
from app.services.attachment_service import (
    AttachmentError,
    MAX_FILE_BYTES,
    VALID_SCOPES,
    list_attachments,
    read_storage_bytes,
    soft_delete_attachment,
    upload_attachment,
)


router = APIRouter(prefix="/attachments", tags=["Attachments"])

# Stream uploads in 1 MiB chunks so we can short-circuit oversized
# bodies before allocating the whole payload in memory.
_UPLOAD_CHUNK_SIZE: int = 1024 * 1024


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    scope: str
    record_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    description: str | None
    has_thumbnail: bool
    sha256: str
    uploaded_at: datetime


def _to_response(a: Attachment) -> AttachmentResponse:
    return AttachmentResponse(
        id=a.id,
        scope=a.scope,
        record_id=a.record_id,
        filename=a.filename,
        content_type=a.content_type,
        size_bytes=a.size_bytes,
        description=a.description,
        has_thumbnail=a.thumbnail_storage_key is not None,
        sha256=a.sha256,
        uploaded_at=a.uploaded_at,
    )


@router.post(
    "/{scope}/{record_id}",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an attachment for a scoped record",
)
async def upload(
    scope: str,
    record_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
    description: str | None = Form(None),
):
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=404, detail="Unsupported attachment scope")

    # Quick pre-check on Content-Length when present. Clients can lie, so
    # the streaming guard below is the source of truth — but rejecting an
    # honest oversized request before we read any body bytes saves both
    # parties bandwidth and worker memory.
    declared_len = file.headers.get("content-length") if file.headers else None
    if declared_len is not None:
        try:
            if int(declared_len) > MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds {MAX_FILE_BYTES // 1024 // 1024} MB limit",
                )
        except ValueError:
            pass  # malformed header — fall through to chunked guard

    # Stream the upload in chunks so we can abort before buffering an
    # oversized body. We allow exactly MAX_FILE_BYTES; the (n+1)th byte
    # trips the guard.
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {MAX_FILE_BYTES // 1024 // 1024} MB limit",
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    try:
        att = await upload_attachment(
            db,
            scope=scope,
            record_id=record_id,
            filename=file.filename or "untitled",
            data=data,
            description=description,
            uploaded_by_user_id=user.id,
        )
    except AttachmentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(att)


@router.get(
    "/{scope}/{record_id}",
    response_model=list[AttachmentResponse],
    summary="List attachments for a scoped record",
)
async def list_for_record(scope: str, record_id: uuid.UUID, user: CurrentUser, db: DB):
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=404, detail="Unsupported attachment scope")
    rows = await list_attachments(db, scope=scope, record_id=record_id)
    return [_to_response(r) for r in rows]


@router.get(
    "/{attachment_id}/download",
    summary="Download an attachment's bytes (server-proxied)",
)
async def download(attachment_id: uuid.UUID, user: CurrentUser, db: DB):
    a = (await db.execute(select(Attachment).where(Attachment.id == attachment_id))).scalar_one_or_none()
    if a is None or a.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        data = read_storage_bytes(a.storage_key)
    except AttachmentError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    return Response(
        content=data,
        media_type=a.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{a.filename}"',
            "Content-Length": str(a.size_bytes),
        },
    )


@router.get(
    "/{attachment_id}/thumbnail",
    summary="Download attachment thumbnail (404 if non-image)",
)
async def thumbnail(attachment_id: uuid.UUID, user: CurrentUser, db: DB):
    a = (await db.execute(select(Attachment).where(Attachment.id == attachment_id))).scalar_one_or_none()
    if a is None or a.deleted_at is not None or a.thumbnail_storage_key is None:
        raise HTTPException(status_code=404, detail="No thumbnail available")
    try:
        data = read_storage_bytes(a.thumbnail_storage_key)
    except AttachmentError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    return Response(content=data, media_type="image/webp")


@router.delete(
    "/{attachment_id}",
    status_code=204,
    summary="Soft-delete an attachment",
)
async def delete(attachment_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        await soft_delete_attachment(
            db, attachment_id=attachment_id, deleted_by_user_id=user.id
        )
    except AttachmentError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await db.commit()
