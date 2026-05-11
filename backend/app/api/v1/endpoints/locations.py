from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.inventory_location import (
    InventoryLocation,
    InventoryTransfer,
    InventoryTransferLine,
    ProductLocationStock,
)
from app.services import product_location_stock_service as pls
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
    # #318 P2: also block when this location is the SoT for any product
    # on-hand. The FK is ondelete=RESTRICT so the DB would reject it
    # anyway, but raising 400 with a clear message beats a generic
    # IntegrityError at the operator.
    stocked = (
        await db.execute(
            select(ProductLocationStock.id).where(
                ProductLocationStock.location_id == location_id,
                ProductLocationStock.on_hand_qty != 0,
            ).limit(1)
        )
    ).first()
    if stocked:
        raise HTTPException(
            status_code=400,
            detail="Location holds product stock; transfer it out or deactivate the location instead",
        )
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
    # #274 P1 (Codex): pre-validate location FKs so a missing from_/to_location_id
    # surfaces as a 404 instead of a Postgres IntegrityError -> 500 on commit.
    requested_ids = {body.from_location_id, body.to_location_id}
    found_ids = set(
        (
            await db.execute(
                select(InventoryLocation.id).where(InventoryLocation.id.in_(requested_ids))
            )
        )
        .scalars()
        .all()
    )
    missing = requested_ids - found_ids
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Location(s) not found: {', '.join(str(i) for i in sorted(missing, key=str))}",
        )

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


# ---------- #318 P2: per-location stock snapshot + default fulfillment location ----------


@router.get(
    "/locations/{location_id}/stock-snapshot",
    summary="#318 P2: per-location product stock derived from completed transfers",
)
async def location_stock_snapshot(location_id: uuid.UUID, user: CurrentUser, db: DB):
    """Returns net qty of each product currently sitting at this location,
    computed from completed transfers (incoming - outgoing). Locations with
    `kind=internal` typically also receive opening stock via the operator's
    starting balance flow; the snapshot reflects only what's been moved.

    For Phase 2-deeper, replace with a real per-location SoT.
    """
    loc = (
        await db.execute(select(InventoryLocation).where(InventoryLocation.id == location_id))
    ).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")

    incoming = (
        await db.execute(
            select(InventoryTransferLine, InventoryTransfer)
            .join(InventoryTransfer, InventoryTransfer.id == InventoryTransferLine.transfer_id)
            .where(
                InventoryTransfer.to_location_id == location_id,
                InventoryTransfer.status == "completed",
                InventoryTransferLine.kind == "product",
            )
        )
    ).all()
    outgoing = (
        await db.execute(
            select(InventoryTransferLine, InventoryTransfer)
            .join(InventoryTransfer, InventoryTransfer.id == InventoryTransferLine.transfer_id)
            .where(
                InventoryTransfer.from_location_id == location_id,
                InventoryTransfer.status == "completed",
                InventoryTransferLine.kind == "product",
            )
        )
    ).all()

    by_product: dict[uuid.UUID, Decimal] = {}
    for line, _ in incoming:
        if line.product_id is None:
            continue
        by_product[line.product_id] = by_product.get(line.product_id, Decimal(0)) + Decimal(line.quantity)
    for line, _ in outgoing:
        if line.product_id is None:
            continue
        by_product[line.product_id] = by_product.get(line.product_id, Decimal(0)) - Decimal(line.quantity)

    return {
        "location_id": str(loc.id),
        "location_name": loc.name,
        "products": [
            {"product_id": str(pid), "qty": str(qty)} for pid, qty in by_product.items()
        ],
    }


# ---------- #318 P2: default fulfillment location setting ----------


_DEFAULT_FULFILLMENT_KEY = "inventory.default_fulfillment_location_id"


class DefaultFulfillmentLocationResponse(BaseModel):
    location_id: uuid.UUID | None


class DefaultFulfillmentLocationUpdate(BaseModel):
    location_id: uuid.UUID | None = None


@router.get(
    "/default-fulfillment-location",
    response_model=DefaultFulfillmentLocationResponse,
    summary="#318 P2: Get the default sale fulfillment location",
)
async def get_default_fulfillment_location(user: CurrentUser, db: DB):
    from app.models.setting import Setting

    row = (
        await db.execute(select(Setting).where(Setting.key == _DEFAULT_FULFILLMENT_KEY))
    ).scalar_one_or_none()
    if row is None or not row.value:
        return DefaultFulfillmentLocationResponse(location_id=None)
    try:
        return DefaultFulfillmentLocationResponse(location_id=uuid.UUID(row.value))
    except ValueError:
        return DefaultFulfillmentLocationResponse(location_id=None)


@router.put(
    "/default-fulfillment-location",
    response_model=DefaultFulfillmentLocationResponse,
    summary="#318 P2: Set or clear the default sale fulfillment location",
)
async def set_default_fulfillment_location(
    body: DefaultFulfillmentLocationUpdate, user: CurrentUser, db: DB
):
    from app.models.setting import Setting

    if body.location_id is not None:
        loc = (
            await db.execute(select(InventoryLocation).where(InventoryLocation.id == body.location_id))
        ).scalar_one_or_none()
        if loc is None:
            raise HTTPException(status_code=404, detail="Location not found")
    row = (
        await db.execute(select(Setting).where(Setting.key == _DEFAULT_FULFILLMENT_KEY))
    ).scalar_one_or_none()
    new_val = str(body.location_id) if body.location_id else ""
    if row is None:
        db.add(Setting(key=_DEFAULT_FULFILLMENT_KEY, value=new_val, notes="Default location used when a sale's fulfillment_location_id is null"))
    else:
        row.value = new_val
    await db.commit()
    return DefaultFulfillmentLocationResponse(location_id=body.location_id)


# ---------- #318 P2: per-location stock SoT + prevent-negative-stock toggle ----------


class LocationStockRow(BaseModel):
    product_id: uuid.UUID
    on_hand_qty: Decimal
    in_transit_to_qty: Decimal
    projected_qty: Decimal


@router.get(
    "/locations/{location_id}/product-stock",
    response_model=list[LocationStockRow],
    summary="#318 P2: per-product on-hand at this location from the SoT",
)
async def location_product_stock(location_id: uuid.UUID, user: CurrentUser, db: DB):
    """Returns the per-(product, location) source-of-truth on-hand,
    plus the in-transit qty arriving from `in_transit` transfers. The
    snapshot endpoint above derives from completed transfers only and
    is retained for back-compat; this endpoint is the authoritative
    read.
    """
    loc = (
        await db.execute(select(InventoryLocation).where(InventoryLocation.id == location_id))
    ).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")

    rows = await pls.stock_by_product_at_location(db, location_id=location_id)
    out: list[LocationStockRow] = []
    for r in rows:
        in_transit = await pls.in_transit_to(
            db, product_id=r.product_id, location_id=location_id
        )
        out.append(
            LocationStockRow(
                product_id=r.product_id,
                on_hand_qty=Decimal(r.on_hand_qty),
                in_transit_to_qty=in_transit,
                projected_qty=Decimal(r.on_hand_qty) + in_transit,
            )
        )
    return out


_PREVENT_NEG_KEY = "inventory.prevent_negative_stock"


class PreventNegativeStockResponse(BaseModel):
    enabled: bool


class PreventNegativeStockUpdate(BaseModel):
    enabled: bool


@router.get(
    "/prevent-negative-stock",
    response_model=PreventNegativeStockResponse,
    summary="#318 P2: read the prevent-negative-stock toggle",
)
async def get_prevent_negative_stock(user: CurrentUser, db: DB):
    from app.models.setting import Setting

    row = (
        await db.execute(select(Setting).where(Setting.key == _PREVENT_NEG_KEY))
    ).scalar_one_or_none()
    enabled = bool(row and (row.value or "").strip().lower() == "true")
    return PreventNegativeStockResponse(enabled=enabled)


@router.put(
    "/prevent-negative-stock",
    response_model=PreventNegativeStockResponse,
    summary="#318 P2: set the prevent-negative-stock toggle (hard-block sales when on)",
)
async def set_prevent_negative_stock(
    body: PreventNegativeStockUpdate, user: CurrentUser, db: DB
):
    from app.models.setting import Setting

    row = (
        await db.execute(select(Setting).where(Setting.key == _PREVENT_NEG_KEY))
    ).scalar_one_or_none()
    new_val = "true" if body.enabled else "false"
    if row is None:
        db.add(
            Setting(
                key=_PREVENT_NEG_KEY,
                value=new_val,
                notes="When true, sales that would drive per-location on-hand below zero are blocked; when false they are warned but allowed.",
            )
        )
    else:
        row.value = new_val
    await db.commit()
    return PreventNegativeStockResponse(enabled=body.enabled)
