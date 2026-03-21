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
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AccountingPeriodCreate,
    AccountingPeriodResponse,
    AccountingPeriodUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
)
from app.services.accounting_service import AccountingValidationError, create_journal_entry

router = APIRouter(prefix="/accounting", tags=["Accounting"])


def _validate_period_dates(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create account (admin only)",
)
async def create_account(body: AccountCreate, admin: CurrentAdmin, db: DB):
    existing = await db.execute(select(Account).where(Account.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account code already exists")

    if body.parent_id:
        parent = (await db.execute(select(Account).where(Account.id == body.parent_id))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")

    account = Account(**body.model_dump(), is_system=False)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.put(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="Update account (admin only)",
)
async def update_account(account_id: uuid.UUID, body: AccountUpdate, admin: CurrentAdmin, db: DB):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    updates = body.model_dump(exclude_unset=True)
    if "parent_id" in updates and updates["parent_id"]:
        parent = (await db.execute(select(Account).where(Account.id == updates["parent_id"]))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
        if parent.id == account.id:
            raise HTTPException(status_code=400, detail="Account cannot be its own parent")

    for field, value in updates.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return account


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


@router.post(
    "/periods",
    response_model=AccountingPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create accounting period (admin only)",
)
async def create_period(body: AccountingPeriodCreate, admin: CurrentAdmin, db: DB):
    _validate_period_dates(body.start_date, body.end_date)
    existing = await db.execute(select(AccountingPeriod).where(AccountingPeriod.period_key == body.period_key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Accounting period key already exists")

    period = AccountingPeriod(**body.model_dump())
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period


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


@router.put(
    "/periods/{period_id}",
    response_model=AccountingPeriodResponse,
    summary="Update accounting period (admin only)",
)
async def update_period(period_id: uuid.UUID, body: AccountingPeriodUpdate, admin: CurrentAdmin, db: DB):
    period = (await db.execute(select(AccountingPeriod).where(AccountingPeriod.id == period_id))).scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Accounting period not found")

    updates = body.model_dump(exclude_unset=True)
    start_date = updates.get("start_date", period.start_date)
    end_date = updates.get("end_date", period.end_date)
    _validate_period_dates(start_date, end_date)

    for field, value in updates.items():
        setattr(period, field, value)

    await db.commit()
    await db.refresh(period)
    return period


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
