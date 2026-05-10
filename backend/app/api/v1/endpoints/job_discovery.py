from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.job_discovery import (
    JobDiscoveryCandidate,
    JobDiscoverySource,
    SUPPORTED_SOURCE_KINDS,
)
from app.services.job_discovery_service import (
    JobDiscoveryError,
    promote_candidate,
    reject_candidate,
    scan_source,
)


router = APIRouter(prefix="/job-discovery", tags=["JobDiscovery"])


# ---------- sources ----------


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: Literal["watch_directory"] = "watch_directory"
    path: str = Field(..., min_length=1, max_length=500)
    file_extensions_csv: str | None = None
    notes: str | None = None
    is_active: bool = True


class SourceUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    path: str | None = Field(None, max_length=500)
    file_extensions_csv: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    path: str
    is_active: bool
    file_extensions_csv: str | None
    last_scan_at: datetime.datetime | None
    notes: str | None


def _src_resp(s: JobDiscoverySource) -> SourceResponse:
    return SourceResponse(
        id=s.id, name=s.name, kind=s.kind, path=s.path,
        is_active=s.is_active, file_extensions_csv=s.file_extensions_csv,
        last_scan_at=s.last_scan_at, notes=s.notes,
    )


@router.get("/sources", response_model=list[SourceResponse], summary="List discovery sources")
async def list_sources(user: CurrentUser, db: DB):
    rows = (await db.execute(select(JobDiscoverySource).order_by(JobDiscoverySource.name))).scalars().all()
    return [_src_resp(s) for s in rows]


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED, summary="Create discovery source")
async def create_source(body: SourceCreate, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    if body.kind not in SUPPORTED_SOURCE_KINDS:
        raise HTTPException(status_code=400, detail=f"Unsupported kind {body.kind!r}")
    s = JobDiscoverySource(**body.model_dump())
    db.add(s)
    await db.commit()
    return _src_resp(s)


@router.patch("/sources/{source_id}", response_model=SourceResponse, summary="Update discovery source")
async def update_source(source_id: uuid.UUID, body: SourceUpdate, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    s = (await db.execute(select(JobDiscoverySource).where(JobDiscoverySource.id == source_id))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    return _src_resp(s)


@router.delete("/sources/{source_id}", status_code=204, summary="Delete discovery source (cascades to candidates)")
async def delete_source(source_id: uuid.UUID, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    s = (await db.execute(select(JobDiscoverySource).where(JobDiscoverySource.id == source_id))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(s)
    await db.commit()


@router.post(
    "/sources/{source_id}/scan",
    summary="Manually trigger a discovery scan against a source",
)
async def scan_source_ep(source_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        result = await scan_source(db, source_id=source_id)
    except JobDiscoveryError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result


# ---------- candidates ----------


class CandidateResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    fingerprint: str
    discovered_at: datetime.datetime
    source_filename: str
    source_path: str | None
    file_size_bytes: int | None
    detected_metadata: dict[str, Any] | None
    status: str
    promoted_job_id: uuid.UUID | None
    parse_warnings: str | None


def _cand_resp(c: JobDiscoveryCandidate) -> CandidateResponse:
    return CandidateResponse(
        id=c.id, source_id=c.source_id, fingerprint=c.fingerprint,
        discovered_at=c.discovered_at, source_filename=c.source_filename,
        source_path=c.source_path, file_size_bytes=c.file_size_bytes,
        detected_metadata=c.detected_metadata, status=c.status,
        promoted_job_id=c.promoted_job_id, parse_warnings=c.parse_warnings,
    )


@router.get("/candidates", response_model=list[CandidateResponse], summary="List discovered candidates")
async def list_candidates(
    user: CurrentUser, db: DB,
    status_filter: str | None = None,
    source_id: uuid.UUID | None = None,
):
    stmt = select(JobDiscoveryCandidate).order_by(JobDiscoveryCandidate.discovered_at.desc())
    if status_filter:
        stmt = stmt.where(JobDiscoveryCandidate.status == status_filter)
    if source_id is not None:
        stmt = stmt.where(JobDiscoveryCandidate.source_id == source_id)
    rows = (await db.execute(stmt.limit(500))).scalars().all()
    return [_cand_resp(c) for c in rows]


class PromoteRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    qty_per_plate: int = Field(..., gt=0)
    num_plates: int = Field(..., gt=0)
    material_id: uuid.UUID
    material_per_plate_g: Decimal = Field(..., gt=0)
    print_time_per_plate_hrs: Decimal = Field(..., gt=0)


@router.post(
    "/candidates/{candidate_id}/promote",
    response_model=CandidateResponse,
    summary="Promote a candidate to a draft Job",
)
async def promote_ep(candidate_id: uuid.UUID, body: PromoteRequest, user: CurrentUser, db: DB):
    try:
        cand = await promote_candidate(db, candidate_id=candidate_id, job_payload=body.model_dump())
    except JobDiscoveryError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _cand_resp(cand)


class RejectRequest(BaseModel):
    reason: str | None = None


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
    summary="Reject a candidate without creating a job",
)
async def reject_ep(candidate_id: uuid.UUID, body: RejectRequest, user: CurrentUser, db: DB):
    try:
        cand = await reject_candidate(db, candidate_id=candidate_id, reason=body.reason)
    except JobDiscoveryError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _cand_resp(cand)
