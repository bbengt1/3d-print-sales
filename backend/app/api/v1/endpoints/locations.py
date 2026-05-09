from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.inventory_location import InventoryLocation, InventoryTransfer, InventoryTransferLine
from app.services.inventory_transfer_service import (
    InventoryTransferError,
    cancel_transfer,
    create_transfer,
    receive_transfer,
    ship_transfer,
)


router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ---------- locations ----------


class LocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: Literal["internal", "consignment", "marketplace"] = "internal"
    notes: str | None = None


class LocationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    kind: Literal["internal", "consignment", "marketplace"] | None = None
    is_active: bool | None = None
    notes: str | None = None


class LocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    is_active: bool
    notes: str | None


@router.get("/locations", response_model=list[LocationResponse], summary="List inventory locations")
async def list_locations(user: CurrentUser, db: DB, include_inactive: bool = False):
    stmt = select(InventoryLocation).order_by(InventoryLocation.name)
    if not include_inactive:
        stmt = stmt.where(InventoryLocation.is_active == True)  # noqa: E712
    rows = (await db.execute(stmt)).scalars().all()
    return [LocationResponse(id=r.id, name=r.name, kind=r.kind, is_active=r.is_active, notes=r.notes) for r in rows]


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED, summary="Create a location")
async def create_location(body: LocationCreate, user: CurrentUser, db: DB):
    existing = (await db.execute(select(InventoryLocation).where(InventoryLocation.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Location '{body.name}' already exists")
    loc = InventoryLocation(name=body.name, kind=body.kind, notes=body.notes)
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return LocationResponse(id=loc.id, name=loc.name, kind=loc.kind, is_active=loc.is_active, notes=loc.notes)


@router.patch("/locations/{location_id}", response_model=LocationResponse, summary="Update a location")
async def update_location(location_id: uuid.UUID, body: LocationUpdate, user: CurrentUser, db: DB):
    loc = (await db.execute(select(InventoryLocation).where(InventoryLocation.id == location_id))).scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(loc, k, v)
    await db.commit()
    return LocationResponse(id=loc.id, name=loc.name, kind=loc.kind, is_active=loc.is_active, notes=loc.notes)


@router.delete("/locations/{location_id}", status_code=204, summary="Delete a location (only if no transfers reference it)")
async def delete_location(location_id: uuid.UUID, user: CurrentUser, db: DB):
    loc = (await db.execute(select(InventoryLocation).where(InventoryLocation.id == location_id))).scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    referenced = (
        await db.execute(
            select(InventoryTransfer.id).where(
                (InventoryTransfer.from_location_id == location_id)
                | (InventoryTransfer.to_location_id == location_id)
            )
        )
    ).first()
    if referenced:
        raise HTTPException(status_code=400, detail="Location is referenced by transfers; deactivate it instead")
    await db.delete(loc)
    await db.commit()


# ---------- transfers ----------


class TransferLineIn(BaseModel):
    kind: Literal["material", "supply", "product"]
    material_id: uuid.UUID | None = None
    supply_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    quantity: Decimal = Field(..., gt=0)


class TransferCreate(BaseModel):
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    lines: list[TransferLineIn] = Field(..., min_length=1)
    notes: str | None = None


class TransferLineOut(BaseModel):
    id: uuid.UUID
    kind: str
    material_id: uuid.UUID | None
    supply_id: uuid.UUID | None
    product_id: uuid.UUID | None
    quantity: Decimal


class TransferResponse(BaseModel):
    id: uuid.UUID
    transfer_number: str
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    status: str
    shipped_at: datetime | None
    received_at: datetime | None
    cancelled_at: datetime | None
    notes: str | None
    lines: list[TransferLineOut]


async def _hydrate(db, transfer: InventoryTransfer) -> TransferResponse:
    lines = (
        await db.execute(
            select(InventoryTransferLine).where(InventoryTransferLine.transfer_id == transfer.id)
        )
    ).scalars().all()
    return TransferResponse(
        id=transfer.id,
        transfer_number=transfer.transfer_number,
        from_location_id=transfer.from_location_id,
        to_location_id=transfer.to_location_id,
        status=transfer.status,
        shipped_at=transfer.shipped_at,
        received_at=transfer.received_at,
        cancelled_at=transfer.cancelled_at,
        notes=transfer.notes,
        lines=[
            TransferLineOut(
                id=l.id,
                kind=l.kind,
                material_id=l.material_id,
                supply_id=l.supply_id,
                product_id=l.product_id,
                quantity=Decimal(l.quantity),
            )
            for l in lines
        ],
    )


@router.get("/transfers", response_model=list[TransferResponse], summary="List transfers")
async def list_transfers(user: CurrentUser, db: DB, status_filter: str | None = None):
    stmt = select(InventoryTransfer).order_by(InventoryTransfer.created_at.desc())
    if status_filter:
        stmt = stmt.where(InventoryTransfer.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _hydrate(db, r) for r in rows]


@router.post("/transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED, summary="Create a transfer")
async def create_transfer_ep(body: TransferCreate, user: CurrentUser, db: DB):
    try:
        transfer = await create_transfer(
            db,
            from_location_id=body.from_location_id,
            to_location_id=body.to_location_id,
            lines=[l.model_dump() for l in body.lines],
            transferred_by_user_id=user.id,
            notes=body.notes,
        )
    except InventoryTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, transfer)


@router.get("/transfers/{transfer_id}", response_model=TransferResponse, summary="Get transfer detail")
async def get_transfer(transfer_id: uuid.UUID, user: CurrentUser, db: DB):
    transfer = (await db.execute(select(InventoryTransfer).where(InventoryTransfer.id == transfer_id))).scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return await _hydrate(db, transfer)


@router.post("/transfers/{transfer_id}/ship", response_model=TransferResponse, summary="Ship a pending transfer")
async def ship_ep(transfer_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        transfer = await ship_transfer(db, transfer_id)
    except InventoryTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, transfer)


@router.post("/transfers/{transfer_id}/receive", response_model=TransferResponse, summary="Receive an in-transit transfer")
async def receive_ep(transfer_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        transfer = await receive_transfer(db, transfer_id)
    except InventoryTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, transfer)


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferResponse, summary="Cancel a pending or in-transit transfer")
async def cancel_ep(transfer_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        transfer = await cancel_transfer(db, transfer_id)
    except InventoryTransferError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, transfer)
