from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.credit_note import CreditNote, CreditNoteLine
from app.models.debit_note import DebitNote, DebitNoteLine
from app.services.note_service import (
    NoteError,
    apply_credit_note,
    apply_debit_note,
    create_credit_note,
    create_debit_note,
    issue_credit_note,
    issue_debit_note,
    refund_credit_note_in_cash,
    void_credit_note,
    void_debit_note,
)


router = APIRouter(tags=["CreditDebitNotes"])


class LineIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    account_id: uuid.UUID


class CreditNoteCreate(BaseModel):
    customer_id: uuid.UUID
    issued_on: date
    original_invoice_id: uuid.UUID | None = None
    reason: str | None = None
    notes: str | None = None
    lines: list[LineIn] = Field(..., min_length=1)


class DebitNoteCreate(BaseModel):
    vendor_id: uuid.UUID
    issued_on: date
    original_bill_id: uuid.UUID | None = None
    reason: str | None = None
    notes: str | None = None
    lines: list[LineIn] = Field(..., min_length=1)


class ApplyRequest(BaseModel):
    target_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    applied_on: date | None = None


def _credit_to_dict(n: CreditNote) -> dict:
    return {
        "id": str(n.id),
        "credit_note_number": n.credit_note_number,
        "customer_id": str(n.customer_id),
        "original_invoice_id": str(n.original_invoice_id) if n.original_invoice_id else None,
        "issued_on": n.issued_on.isoformat(),
        "status": n.status,
        "reason": n.reason,
        "subtotal_amount": str(Decimal(n.subtotal_amount)),
        "total_amount": str(Decimal(n.total_amount)),
        "applied_amount": str(Decimal(n.applied_amount)),
        "journal_entry_id": str(n.journal_entry_id) if n.journal_entry_id else None,
        "notes": n.notes,
    }


def _debit_to_dict(n: DebitNote) -> dict:
    return {
        "id": str(n.id),
        "debit_note_number": n.debit_note_number,
        "vendor_id": str(n.vendor_id),
        "original_bill_id": str(n.original_bill_id) if n.original_bill_id else None,
        "issued_on": n.issued_on.isoformat(),
        "status": n.status,
        "reason": n.reason,
        "subtotal_amount": str(Decimal(n.subtotal_amount)),
        "total_amount": str(Decimal(n.total_amount)),
        "applied_amount": str(Decimal(n.applied_amount)),
        "journal_entry_id": str(n.journal_entry_id) if n.journal_entry_id else None,
        "notes": n.notes,
    }


# ---------- credit notes ----------


@router.post("/credit-notes", status_code=status.HTTP_201_CREATED, summary="Create a draft credit note")
async def create_cn(body: CreditNoteCreate, user: CurrentUser, db: DB):
    try:
        n = await create_credit_note(
            db,
            customer_id=body.customer_id,
            issued_on=body.issued_on,
            lines=[l.model_dump(mode="json") for l in body.lines],
            original_invoice_id=body.original_invoice_id,
            reason=body.reason,
            notes=body.notes,
        )
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _credit_to_dict(n)


@router.get("/credit-notes", summary="List credit notes")
async def list_cn(user: CurrentUser, db: DB, customer_id: uuid.UUID | None = None, status_filter: str | None = None):
    stmt = select(CreditNote).order_by(CreditNote.issued_on.desc())
    if customer_id:
        stmt = stmt.where(CreditNote.customer_id == customer_id)
    if status_filter:
        stmt = stmt.where(CreditNote.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_credit_to_dict(r) for r in rows]


@router.get("/credit-notes/{note_id}", summary="Credit note detail")
async def get_cn(note_id: uuid.UUID, user: CurrentUser, db: DB):
    n = (await db.execute(select(CreditNote).where(CreditNote.id == note_id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="Credit note not found")
    lines = (
        await db.execute(select(CreditNoteLine).where(CreditNoteLine.credit_note_id == n.id))
    ).scalars().all()
    return {
        **_credit_to_dict(n),
        "lines": [
            {
                "id": str(l.id),
                "description": l.description,
                "quantity": str(Decimal(l.quantity)),
                "unit_price": str(Decimal(l.unit_price)),
                "line_total": str(Decimal(l.line_total)),
                "account_id": str(l.account_id),
            }
            for l in lines
        ],
    }


@router.post("/credit-notes/{note_id}/issue", summary="Issue (post JE) a draft credit note")
async def issue_cn(note_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        n = await issue_credit_note(db, note_id)
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _credit_to_dict(n)


@router.post("/credit-notes/{note_id}/apply", summary="Apply credit note to an invoice")
async def apply_cn(note_id: uuid.UUID, body: ApplyRequest, user: CurrentUser, db: DB):
    try:
        app = await apply_credit_note(
            db,
            note_id=note_id,
            invoice_id=body.target_id,
            amount=body.amount,
            applied_on=body.applied_on,
        )
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {
        "id": str(app.id),
        "credit_note_id": str(app.credit_note_id),
        "invoice_id": str(app.invoice_id),
        "amount": str(Decimal(app.amount)),
        "applied_on": app.applied_on.isoformat(),
    }


class RefundInCashRequest(BaseModel):
    cash_account_id: uuid.UUID
    paid_on: date | None = None


@router.post(
    "/credit-notes/{note_id}/refund-in-cash",
    summary="#321 P2: Refund the unapplied portion of a credit note as cash",
)
async def refund_in_cash(note_id: uuid.UUID, body: RefundInCashRequest, user: CurrentUser, db: DB):
    try:
        n = await refund_credit_note_in_cash(
            db,
            note_id=note_id,
            cash_account_id=body.cash_account_id,
            paid_on=body.paid_on,
        )
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _credit_to_dict(n)


@router.post("/credit-notes/{note_id}/void", summary="Void a credit note (reverses issue JE)")
async def void_cn(note_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        n = await void_credit_note(db, note_id)
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _credit_to_dict(n)


# ---------- debit notes (mirror) ----------


@router.post("/debit-notes", status_code=status.HTTP_201_CREATED, summary="Create a draft debit note")
async def create_dn(body: DebitNoteCreate, user: CurrentUser, db: DB):
    try:
        n = await create_debit_note(
            db,
            vendor_id=body.vendor_id,
            issued_on=body.issued_on,
            lines=[l.model_dump(mode="json") for l in body.lines],
            original_bill_id=body.original_bill_id,
            reason=body.reason,
            notes=body.notes,
        )
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _debit_to_dict(n)


@router.get("/debit-notes", summary="List debit notes")
async def list_dn(user: CurrentUser, db: DB, vendor_id: uuid.UUID | None = None, status_filter: str | None = None):
    stmt = select(DebitNote).order_by(DebitNote.issued_on.desc())
    if vendor_id:
        stmt = stmt.where(DebitNote.vendor_id == vendor_id)
    if status_filter:
        stmt = stmt.where(DebitNote.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_debit_to_dict(r) for r in rows]


@router.get("/debit-notes/{note_id}", summary="Debit note detail")
async def get_dn(note_id: uuid.UUID, user: CurrentUser, db: DB):
    n = (await db.execute(select(DebitNote).where(DebitNote.id == note_id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="Debit note not found")
    lines = (
        await db.execute(select(DebitNoteLine).where(DebitNoteLine.debit_note_id == n.id))
    ).scalars().all()
    return {
        **_debit_to_dict(n),
        "lines": [
            {
                "id": str(l.id),
                "description": l.description,
                "quantity": str(Decimal(l.quantity)),
                "unit_price": str(Decimal(l.unit_price)),
                "line_total": str(Decimal(l.line_total)),
                "account_id": str(l.account_id),
            }
            for l in lines
        ],
    }


@router.post("/debit-notes/{note_id}/issue", summary="Issue (post JE) a draft debit note")
async def issue_dn(note_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        n = await issue_debit_note(db, note_id)
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _debit_to_dict(n)


@router.post("/debit-notes/{note_id}/apply", summary="Apply debit note to a bill")
async def apply_dn(note_id: uuid.UUID, body: ApplyRequest, user: CurrentUser, db: DB):
    try:
        app = await apply_debit_note(
            db,
            note_id=note_id,
            bill_id=body.target_id,
            amount=body.amount,
            applied_on=body.applied_on,
        )
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {
        "id": str(app.id),
        "debit_note_id": str(app.debit_note_id),
        "bill_id": str(app.bill_id),
        "amount": str(Decimal(app.amount)),
        "applied_on": app.applied_on.isoformat(),
    }


@router.post("/debit-notes/{note_id}/void", summary="Void a debit note (reverses issue JE)")
async def void_dn(note_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        n = await void_debit_note(db, note_id)
    except NoteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _debit_to_dict(n)
