from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.inter_account_transfer import InterAccountTransfer
from app.services.inter_account_transfer_service import (
    InterAccountTransferError,
    create_inter_account_transfer,
    delete_inter_account_transfer,
    edit_inter_account_transfer,
)


router = APIRouter(prefix="/banking/inter-account-transfers", tags=["Banking"])


class TransferCreate(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    paid_on: date
    received_on: date | None = None
    notes: str | None = None


class TransferResponse(BaseModel):
    id: uuid.UUID
    transfer_number: str
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal
    paid_on: date
    received_on: date
    journal_entry_id: uuid.UUID
    notes: str | None
    created_at: datetime


def _to_response(t: InterAccountTransfer) -> TransferResponse:
    return TransferResponse(
        id=t.id,
        transfer_number=t.transfer_number,
        from_account_id=t.from_account_id,
        to_account_id=t.to_account_id,
        amount=Decimal(t.amount),
        paid_on=t.paid_on,
        received_on=t.received_on,
        journal_entry_id=t.journal_entry_id,
        notes=t.notes,
        created_at=t.created_at,
    )


@router.get("", response_model=list[TransferResponse], summary="List inter-account transfers")
async def list_iat(user: CurrentUser, db: DB):
    rows = (
        await db.execute(select(InterAccountTransfer).order_by(InterAccountTransfer.paid_on.desc()))
    ).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED, summary="Create inter-account transfer")
async def create_iat(body: TransferCreate, user: CurrentUser, db: DB):
    try:
        t = await create_inter_account_transfer(
            db,
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=body.amount,
            paid_on=body.paid_on,
            received_on=body.received_on,
            notes=body.notes,
        )
    except InterAccountTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(t)


@router.get("/{transfer_id}", response_model=TransferResponse, summary="Get inter-account transfer detail")
async def get_iat(transfer_id: uuid.UUID, user: CurrentUser, db: DB):
    t = (await db.execute(select(InterAccountTransfer).where(InterAccountTransfer.id == transfer_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return _to_response(t)


class TransferEdit(BaseModel):
    amount: Decimal | None = Field(None, gt=0)
    paid_on: date | None = None
    received_on: date | None = None
    notes: str | None = None


@router.patch("/{transfer_id}", response_model=TransferResponse, summary="Edit inter-account transfer (refused if either leg is reconciled)")
async def edit_iat(transfer_id: uuid.UUID, body: TransferEdit, user: CurrentUser, db: DB):
    try:
        t = await edit_inter_account_transfer(
            db,
            transfer_id,
            amount=body.amount,
            paid_on=body.paid_on,
            received_on=body.received_on,
            notes=body.notes,
        )
    except InterAccountTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(t)


@router.delete("/{transfer_id}", status_code=204, summary="Delete inter-account transfer (refused if either leg is reconciled)")
async def delete_iat(transfer_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        await delete_inter_account_transfer(db, transfer_id)
    except InterAccountTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
