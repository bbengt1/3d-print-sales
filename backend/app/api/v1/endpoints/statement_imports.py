from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.statement_import import StatementImport, StatementLine
from app.services.statement_import_service import (
    StatementImportError,
    ignore_line,
    import_statement,
    match_line,
    suggest_matches,
)


router = APIRouter(prefix="/banking/imports", tags=["Banking"])


class StatementImportResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    source_format: str
    source_filename: str
    line_count: int
    duplicate_count: int
    status: str
    notes: str | None
    created_at: datetime


class StatementLineResponse(BaseModel):
    id: uuid.UUID
    import_id: uuid.UUID
    account_id: uuid.UUID
    posted_date: date
    amount: Decimal
    description: str
    fitid: str | None
    match_status: str
    matched_journal_line_id: uuid.UUID | None


class JournalLineSuggestion(BaseModel):
    id: uuid.UUID
    journal_entry_id: uuid.UUID
    entry_type: str
    amount: Decimal
    description: str | None


class MatchRequest(BaseModel):
    journal_line_id: uuid.UUID


def _to_import(i: StatementImport) -> StatementImportResponse:
    return StatementImportResponse(
        id=i.id,
        account_id=i.account_id,
        source_format=i.source_format,
        source_filename=i.source_filename,
        line_count=i.line_count,
        duplicate_count=i.duplicate_count,
        status=i.status,
        notes=i.notes,
        created_at=i.created_at,
    )


def _to_line(l: StatementLine) -> StatementLineResponse:
    return StatementLineResponse(
        id=l.id,
        import_id=l.import_id,
        account_id=l.account_id,
        posted_date=l.posted_date,
        amount=Decimal(l.amount),
        description=l.description,
        fitid=l.fitid,
        match_status=l.match_status,
        matched_journal_line_id=l.matched_journal_line_id,
    )


@router.post(
    "",
    response_model=StatementImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a statement file (OFX or CSV)",
)
async def upload_import(
    user: CurrentUser,
    db: DB,
    account_id: uuid.UUID = Form(...),
    source_format: Literal["ofx", "csv"] = Form("ofx"),
    file: UploadFile = File(...),
):
    content = await file.read()
    try:
        imp = await import_statement(
            db,
            account_id=account_id,
            source_format=source_format,
            source_filename=file.filename or "(unnamed)",
            content=content,
            imported_by_user_id=user.id,
        )
    except StatementImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_import(imp)


@router.get("", response_model=list[StatementImportResponse], summary="List statement imports")
async def list_imports(user: CurrentUser, db: DB, account_id: uuid.UUID | None = None):
    stmt = select(StatementImport).order_by(StatementImport.created_at.desc())
    if account_id is not None:
        stmt = stmt.where(StatementImport.account_id == account_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_import(r) for r in rows]


@router.get("/{import_id}/lines", response_model=list[StatementLineResponse], summary="List lines for an import")
async def list_lines(import_id: uuid.UUID, user: CurrentUser, db: DB, status_filter: str | None = None):
    stmt = select(StatementLine).where(StatementLine.import_id == import_id).order_by(StatementLine.posted_date)
    if status_filter:
        stmt = stmt.where(StatementLine.match_status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_line(r) for r in rows]


@router.get("/lines/{statement_line_id}/suggestions", response_model=list[JournalLineSuggestion], summary="Get match suggestions for a statement line")
async def suggestions_ep(statement_line_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        rows = await suggest_matches(db, statement_line_id=statement_line_id, limit=5)
    except StatementImportError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [
        JournalLineSuggestion(
            id=r.id,
            journal_entry_id=r.journal_entry_id,
            entry_type=r.entry_type,
            amount=Decimal(r.amount),
            description=r.description,
        )
        for r in rows
    ]


@router.post("/lines/{statement_line_id}/match", response_model=StatementLineResponse, summary="Match a statement line to an existing journal line")
async def match_ep(statement_line_id: uuid.UUID, body: MatchRequest, user: CurrentUser, db: DB):
    try:
        sl = await match_line(
            db, statement_line_id=statement_line_id, journal_line_id=body.journal_line_id
        )
    except StatementImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_line(sl)


@router.post("/lines/{statement_line_id}/ignore", response_model=StatementLineResponse, summary="Ignore a statement line")
async def ignore_ep(statement_line_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        sl = await ignore_line(db, statement_line_id)
    except StatementImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_line(sl)
