from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.delivery_note import DeliveryNote, DeliveryNoteLine
from app.services.reference_number_service import next_number


router = APIRouter(prefix="/delivery-notes", tags=["DeliveryNotes"])


class LineIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., gt=0)
    notes: str | None = Field(None, max_length=500)


class DNCreate(BaseModel):
    invoice_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200)
    issued_on: date
    shipped_on: date | None = None
    tracking_number: str | None = Field(None, max_length=120)
    notes: str | None = None
    lines: list[LineIn] = Field(..., min_length=1)


class DNUpdate(BaseModel):
    shipped_on: date | None = None
    tracking_number: str | None = Field(None, max_length=120)
    # `status` is optional-by-omission, but if the client sends the key it
    # must be a valid non-null value. The underlying column is non-nullable,
    # so accepting `null` here would surface as a 500 at commit time
    # (Codex P1 review on PR #291).
    status: Literal["draft", "shipped", "delivered", "cancelled"] | None = None
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def _status_not_null(cls, v):
        if v is None:
            raise ValueError("status may not be null")
        return v


def _to_dict(dn: DeliveryNote) -> dict:
    return {
        "id": str(dn.id),
        "delivery_note_number": dn.delivery_note_number,
        "invoice_id": str(dn.invoice_id) if dn.invoice_id else None,
        "customer_id": str(dn.customer_id) if dn.customer_id else None,
        "customer_name": dn.customer_name,
        "issued_on": dn.issued_on.isoformat(),
        "shipped_on": dn.shipped_on.isoformat() if dn.shipped_on else None,
        "tracking_number": dn.tracking_number,
        "status": dn.status,
        "notes": dn.notes,
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a delivery note (draft)")
async def create_dn(body: DNCreate, user: CurrentUser, db: DB):
    if not body.invoice_id and not body.customer_id and not body.customer_name:
        raise HTTPException(status_code=400, detail="invoice_id, customer_id, or customer_name required")
    number = await next_number(db, "delivery_note")
    dn = DeliveryNote(
        delivery_note_number=number,
        invoice_id=body.invoice_id,
        customer_id=body.customer_id,
        customer_name=body.customer_name,
        issued_on=body.issued_on,
        shipped_on=body.shipped_on,
        tracking_number=body.tracking_number,
        notes=body.notes,
    )
    db.add(dn)
    await db.flush()
    for line in body.lines:
        db.add(
            DeliveryNoteLine(
                delivery_note_id=dn.id,
                description=line.description,
                quantity=line.quantity,
                notes=line.notes,
            )
        )
    await db.commit()
    return _to_dict(dn)


@router.get("", summary="List delivery notes")
async def list_dn(user: CurrentUser, db: DB, invoice_id: uuid.UUID | None = None, status_filter: str | None = None):
    stmt = select(DeliveryNote).order_by(DeliveryNote.issued_on.desc())
    if invoice_id:
        stmt = stmt.where(DeliveryNote.invoice_id == invoice_id)
    if status_filter:
        stmt = stmt.where(DeliveryNote.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_dict(r) for r in rows]


@router.get("/{dn_id}", summary="Delivery note detail")
async def get_dn(dn_id: uuid.UUID, user: CurrentUser, db: DB):
    dn = (await db.execute(select(DeliveryNote).where(DeliveryNote.id == dn_id))).scalar_one_or_none()
    if not dn:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    lines = (await db.execute(select(DeliveryNoteLine).where(DeliveryNoteLine.delivery_note_id == dn.id))).scalars().all()
    return {
        **_to_dict(dn),
        "lines": [
            {
                "id": str(l.id),
                "description": l.description,
                "quantity": str(Decimal(l.quantity)),
                "notes": l.notes,
            }
            for l in lines
        ],
    }


@router.patch("/{dn_id}", summary="Update delivery status / tracking / notes")
async def update_dn(dn_id: uuid.UUID, body: DNUpdate, user: CurrentUser, db: DB):
    dn = (await db.execute(select(DeliveryNote).where(DeliveryNote.id == dn_id))).scalar_one_or_none()
    if not dn:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(dn, k, v)
    await db.commit()
    return _to_dict(dn)


@router.delete("/{dn_id}", status_code=204, summary="Delete a delivery note (only allowed in draft state)")
async def delete_dn(dn_id: uuid.UUID, user: CurrentUser, db: DB):
    dn = (await db.execute(select(DeliveryNote).where(DeliveryNote.id == dn_id))).scalar_one_or_none()
    if not dn:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    if dn.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot delete a {dn.status} delivery note")
    await db.delete(dn)
    await db.commit()
