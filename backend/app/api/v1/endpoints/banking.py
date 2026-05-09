from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.account import Account
from app.models.bank_reconciliation import BankReconciliation
from app.models.journal_entry import JournalEntry
from app.services.bank_reconciliation_service import (
    BankReconciliationError,
    compute_account_balance,
    compute_book_balance,
    exclude_line,
    finalize_reconciliation,
    include_line,
    list_eligible_lines,
    reopen_reconciliation,
    start_reconciliation,
)


router = APIRouter(prefix="/banking", tags=["Banking"])


# ----------- account flagging -----------


class BankAccountFlagRequest(BaseModel):
    is_bank_account: bool
    bank_account_kind: Literal[
        "checking", "savings", "credit_card", "payment_processor"
    ] | None = None


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    account_type: str
    is_bank_account: bool
    bank_account_kind: str | None
    running_balance: Decimal


@router.get("/accounts", response_model=list[BankAccountResponse], summary="List bank-typed accounts with running balance")
async def list_bank_accounts(user: CurrentUser, db: DB):
    accounts = (
        await db.execute(
            select(Account).where(Account.is_bank_account == True, Account.is_active == True)  # noqa: E712
        )
    ).scalars().all()
    out: list[BankAccountResponse] = []
    for a in accounts:
        bal = await compute_account_balance(db, a.id)
        out.append(
            BankAccountResponse(
                id=a.id,
                code=a.code,
                name=a.name,
                account_type=a.account_type,
                is_bank_account=a.is_bank_account,
                bank_account_kind=a.bank_account_kind,
                running_balance=bal,
            )
        )
    return out


@router.patch("/accounts/{account_id}/flag", response_model=BankAccountResponse, summary="Flag or unflag a GL account as a bank account")
async def flag_bank_account(account_id: uuid.UUID, body: BankAccountFlagRequest, user: CurrentUser, db: DB):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.is_bank_account = body.is_bank_account
    account.bank_account_kind = body.bank_account_kind if body.is_bank_account else None
    await db.commit()
    bal = await compute_account_balance(db, account.id)
    return BankAccountResponse(
        id=account.id,
        code=account.code,
        name=account.name,
        account_type=account.account_type,
        is_bank_account=account.is_bank_account,
        bank_account_kind=account.bank_account_kind,
        running_balance=bal,
    )


# ----------- reconciliations -----------


class ReconciliationCreateRequest(BaseModel):
    account_id: uuid.UUID
    statement_end_date: date
    statement_ending_balance: Decimal = Field(...)
    notes: str | None = None


class ReconciliationLineToggle(BaseModel):
    journal_line_id: uuid.UUID
    included: bool


class JournalLineDTO(BaseModel):
    id: uuid.UUID
    journal_entry_id: uuid.UUID
    entry_date: date
    description: str | None
    entry_type: str
    amount: Decimal
    cleared_status: str


class ReconciliationDetailResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    statement_end_date: date
    statement_ending_balance: Decimal
    opening_balance: Decimal
    book_balance: Decimal
    variance: Decimal
    status: str
    finalized_at: datetime | None
    notes: str | None
    eligible_lines: list[JournalLineDTO]
    included_line_ids: list[uuid.UUID]


async def _hydrate_recon(db, recon: BankReconciliation) -> ReconciliationDetailResponse:
    eligible = await list_eligible_lines(
        db, account_id=recon.account_id, statement_end_date=recon.statement_end_date
    )
    eligible_dtos = [
        JournalLineDTO(
            id=line.id,
            journal_entry_id=line.journal_entry_id,
            entry_date=entry.entry_date,
            description=line.description,
            entry_type=line.entry_type,
            amount=Decimal(line.amount),
            cleared_status=line.cleared_status,
        )
        for line, entry in eligible
    ]
    book = await compute_book_balance(db, recon.id)
    from app.models.bank_reconciliation import BankReconciliationLine
    included_ids = [
        r.journal_line_id
        for r in (
            await db.execute(
                select(BankReconciliationLine).where(BankReconciliationLine.reconciliation_id == recon.id)
            )
        ).scalars().all()
    ]
    return ReconciliationDetailResponse(
        id=recon.id,
        account_id=recon.account_id,
        statement_end_date=recon.statement_end_date,
        statement_ending_balance=Decimal(recon.statement_ending_balance),
        opening_balance=Decimal(recon.opening_balance),
        book_balance=book,
        variance=book - Decimal(recon.statement_ending_balance),
        status=recon.status,
        finalized_at=recon.finalized_at,
        notes=recon.notes,
        eligible_lines=eligible_dtos,
        included_line_ids=included_ids,
    )


@router.post("/reconciliations", response_model=ReconciliationDetailResponse, status_code=status.HTTP_201_CREATED, summary="Start a reconciliation")
async def create_reconciliation(body: ReconciliationCreateRequest, user: CurrentUser, db: DB):
    try:
        recon = await start_reconciliation(
            db,
            account_id=body.account_id,
            statement_end_date=body.statement_end_date,
            statement_ending_balance=body.statement_ending_balance,
            notes=body.notes,
        )
    except BankReconciliationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate_recon(db, recon)


@router.get("/reconciliations", summary="List reconciliations (filtered by account/status)")
async def list_reconciliations(user: CurrentUser, db: DB, account_id: uuid.UUID | None = None, recon_status: str | None = None):
    stmt = select(BankReconciliation).order_by(BankReconciliation.statement_end_date.desc())
    if account_id is not None:
        stmt = stmt.where(BankReconciliation.account_id == account_id)
    if recon_status is not None:
        stmt = stmt.where(BankReconciliation.status == recon_status)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "statement_end_date": r.statement_end_date,
            "statement_ending_balance": Decimal(r.statement_ending_balance),
            "status": r.status,
            "finalized_at": r.finalized_at,
        }
        for r in rows
    ]


@router.get("/reconciliations/{reconciliation_id}", response_model=ReconciliationDetailResponse, summary="Get reconciliation detail")
async def get_reconciliation(reconciliation_id: uuid.UUID, user: CurrentUser, db: DB):
    recon = (await db.execute(select(BankReconciliation).where(BankReconciliation.id == reconciliation_id))).scalar_one_or_none()
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    return await _hydrate_recon(db, recon)


@router.patch("/reconciliations/{reconciliation_id}/toggle-line", response_model=ReconciliationDetailResponse, summary="Include or exclude a journal line in the reconciliation")
async def toggle_recon_line(reconciliation_id: uuid.UUID, body: ReconciliationLineToggle, user: CurrentUser, db: DB):
    try:
        if body.included:
            await include_line(db, reconciliation_id=reconciliation_id, journal_line_id=body.journal_line_id)
        else:
            await exclude_line(db, reconciliation_id=reconciliation_id, journal_line_id=body.journal_line_id)
    except BankReconciliationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    recon = (await db.execute(select(BankReconciliation).where(BankReconciliation.id == reconciliation_id))).scalar_one()
    return await _hydrate_recon(db, recon)


@router.post("/reconciliations/{reconciliation_id}/finalize", response_model=ReconciliationDetailResponse, summary="Finalize a reconciliation (refuses if book != statement)")
async def finalize_recon(reconciliation_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        recon = await finalize_reconciliation(
            db, reconciliation_id=reconciliation_id, finalized_by_user_id=user.id
        )
    except BankReconciliationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate_recon(db, recon)


@router.post("/reconciliations/{reconciliation_id}/reopen", response_model=ReconciliationDetailResponse, summary="Reopen a finalized reconciliation (admin)")
async def reopen_recon(reconciliation_id: uuid.UUID, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can reopen a finalized reconciliation")
    try:
        recon = await reopen_reconciliation(db, reconciliation_id=reconciliation_id)
    except BankReconciliationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate_recon(db, recon)
