from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentAdmin
from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.journal_entry import JournalEntry
from app.schemas.accounting import (
    AccountResponse,
    AccountingPeriodResponse,
    JournalEntryCreate,
    JournalEntryResponse,
)
from app.services.accounting_service import AccountingValidationError, create_journal_entry

router = APIRouter(prefix="/accounting", tags=["Accounting"])


@router.get(
    "/accounts",
    response_model=list[AccountResponse],
    summary="List chart of accounts (admin only)",
)
async def list_accounts(
    admin: CurrentAdmin,
    db: DB,
    is_active: bool | None = Query(None),
    account_type: str | None = Query(None),
):
    stmt = select(Account).order_by(Account.code.asc())
    if is_active is not None:
        stmt = stmt.where(Account.is_active == is_active)
    if account_type:
        stmt = stmt.where(Account.account_type == account_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/periods",
    response_model=list[AccountingPeriodResponse],
    summary="List accounting periods (admin only)",
)
async def list_periods(admin: CurrentAdmin, db: DB, status_filter: str | None = Query(None, alias="status")):
    stmt = select(AccountingPeriod).order_by(AccountingPeriod.start_date.desc())
    if status_filter:
        stmt = stmt.where(AccountingPeriod.status == status_filter)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/journal-entries",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post a journal entry (admin only)",
)
async def create_entry(body: JournalEntryCreate, admin: CurrentAdmin, db: DB):
    try:
        entry = await create_journal_entry(db, body)
    except AccountingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry.id)
    )
    return result.scalar_one()


@router.get(
    "/journal-entries",
    response_model=list[JournalEntryResponse],
    summary="List journal entries (admin only)",
)
async def list_entries(
    admin: CurrentAdmin,
    db: DB,
    status_filter: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    stmt = select(JournalEntry).options(selectinload(JournalEntry.lines)).order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    if status_filter:
        stmt = stmt.where(JournalEntry.status == status_filter)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/journal-entries/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Get journal entry by ID (admin only)",
)
async def get_entry(entry_id: uuid.UUID, admin: CurrentAdmin, db: DB):
    result = await db.execute(
        select(JournalEntry).options(selectinload(JournalEntry.lines)).where(JournalEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry
