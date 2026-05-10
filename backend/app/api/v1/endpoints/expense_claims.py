from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.expense_claim import ExpenseClaim, ExpenseClaimLine
from app.services.expense_claim_service import (
    ExpenseClaimError,
    approve_claim,
    cancel_claim,
    create_claim,
    reimburse_claim,
    submit_claim,
)


router = APIRouter(prefix="/expense-claims", tags=["ExpenseClaims"])


class LineIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    expense_account_id: uuid.UUID
    # `amount` ignored when `line_kind=mileage` (computed from miles × rate).
    amount: Decimal = Field(0, ge=0)
    line_kind: Literal["expense", "mileage"] = "expense"
    miles: Decimal | None = Field(None, gt=0)
    notes: str | None = None


class ClaimCreate(BaseModel):
    payer_kind: Literal["owner", "employee", "contractor"] = "owner"
    payer_name: str = Field(..., min_length=1, max_length=200)
    notes: str | None = None
    lines: list[LineIn] = Field(..., min_length=1)


class LineOut(BaseModel):
    id: uuid.UUID
    description: str
    expense_account_id: uuid.UUID
    amount: Decimal
    line_kind: str = "expense"
    miles: Decimal | None = None
    mileage_rate_used: Decimal | None = None
    notes: str | None


class ClaimResponse(BaseModel):
    id: uuid.UUID
    claim_number: str
    payer_kind: str
    payer_name: str
    submitted_on: date | None
    status: str
    total_amount: Decimal
    journal_entry_id: uuid.UUID | None
    reimbursement_journal_entry_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    lines: list[LineOut]


class ApproveRequest(BaseModel):
    approve_date: date | None = None


class ReimburseRequest(BaseModel):
    cash_account_id: uuid.UUID
    paid_on: date | None = None


async def _hydrate(db, claim: ExpenseClaim) -> ClaimResponse:
    lines = (
        await db.execute(
            select(ExpenseClaimLine).where(ExpenseClaimLine.claim_id == claim.id)
        )
    ).scalars().all()
    return ClaimResponse(
        id=claim.id,
        claim_number=claim.claim_number,
        payer_kind=claim.payer_kind,
        payer_name=claim.payer_name,
        submitted_on=claim.submitted_on,
        status=claim.status,
        total_amount=Decimal(claim.total_amount),
        journal_entry_id=claim.journal_entry_id,
        reimbursement_journal_entry_id=claim.reimbursement_journal_entry_id,
        notes=claim.notes,
        created_at=claim.created_at,
        lines=[
            LineOut(
                id=l.id,
                description=l.description,
                expense_account_id=l.expense_account_id,
                amount=Decimal(l.amount),
                line_kind=l.line_kind,
                miles=Decimal(l.miles) if l.miles is not None else None,
                mileage_rate_used=Decimal(l.mileage_rate_used) if l.mileage_rate_used is not None else None,
                notes=l.notes,
            )
            for l in lines
        ],
    )


@router.get("", response_model=list[ClaimResponse], summary="List expense claims")
async def list_claims(user: CurrentUser, db: DB, status_filter: str | None = None):
    stmt = select(ExpenseClaim).order_by(ExpenseClaim.created_at.desc())
    if status_filter:
        stmt = stmt.where(ExpenseClaim.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _hydrate(db, r) for r in rows]


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED, summary="Create an expense claim")
async def create(body: ClaimCreate, user: CurrentUser, db: DB):
    try:
        claim = await create_claim(
            db,
            payer_kind=body.payer_kind,
            payer_name=body.payer_name,
            notes=body.notes,
            lines=[l.model_dump() for l in body.lines],
        )
    except ExpenseClaimError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, claim)


@router.get("/{claim_id}", response_model=ClaimResponse, summary="Get claim detail")
async def get_one(claim_id: uuid.UUID, user: CurrentUser, db: DB):
    claim = (await db.execute(select(ExpenseClaim).where(ExpenseClaim.id == claim_id))).scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    return await _hydrate(db, claim)


@router.post("/{claim_id}/submit", response_model=ClaimResponse, summary="Submit a draft claim")
async def submit_ep(claim_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        claim = await submit_claim(db, claim_id)
    except ExpenseClaimError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, claim)


@router.post("/{claim_id}/approve", response_model=ClaimResponse, summary="Approve a claim and post the JE")
async def approve_ep(claim_id: uuid.UUID, body: ApproveRequest, user: CurrentUser, db: DB):
    try:
        claim = await approve_claim(db, claim_id, approve_date=body.approve_date)
    except ExpenseClaimError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, claim)


@router.post("/{claim_id}/reimburse", response_model=ClaimResponse, summary="Reimburse an approved claim")
async def reimburse_ep(claim_id: uuid.UUID, body: ReimburseRequest, user: CurrentUser, db: DB):
    try:
        claim = await reimburse_claim(
            db, claim_id, cash_account_id=body.cash_account_id, paid_on=body.paid_on
        )
    except ExpenseClaimError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, claim)


@router.post("/{claim_id}/cancel", response_model=ClaimResponse, summary="Cancel a claim")
async def cancel_ep(claim_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        claim = await cancel_claim(db, claim_id)
    except ExpenseClaimError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, claim)
