from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentUser
from app.models.supply import Supply
from app.schemas.supply import SupplyAdjust, SupplyCreate, SupplyResponse, SupplyUpdate

router = APIRouter(prefix="/supplies", tags=["Supplies"])


@router.get(
    "",
    response_model=list[SupplyResponse],
    summary="List supplies",
    description="Returns purchased/shop supplies with optional active, category, and text filtering.",
)
async def list_supplies(
    db: DB,
    active: bool | None = Query(None, description="Filter by active status"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search by name, SKU, category, or supplier"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    stmt = select(Supply)
    if active is not None:
        stmt = stmt.where(Supply.active == active)
    if category:
        stmt = stmt.where(Supply.category == category)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Supply.name.ilike(pattern)
            | Supply.sku.ilike(pattern)
            | Supply.category.ilike(pattern)
            | Supply.supplier.ilike(pattern)
        )
    result = await db.execute(stmt.order_by(Supply.name.asc()).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{supply_id}", response_model=SupplyResponse, summary="Get supply by ID")
async def get_supply(supply_id: uuid.UUID, db: DB):
    supply = (await db.execute(select(Supply).where(Supply.id == supply_id))).scalar_one_or_none()
    if not supply:
        raise HTTPException(status_code=404, detail="Supply not found")
    return supply


@router.post("", response_model=SupplyResponse, status_code=201, summary="Create a supply")
async def create_supply(body: SupplyCreate, user: CurrentUser, db: DB):
    supply = Supply(**body.model_dump())
    db.add(supply)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Supply SKU already exists") from exc
    await db.refresh(supply)
    return supply


@router.put("/{supply_id}", response_model=SupplyResponse, summary="Update a supply")
async def update_supply(supply_id: uuid.UUID, body: SupplyUpdate, user: CurrentUser, db: DB):
    supply = (await db.execute(select(Supply).where(Supply.id == supply_id))).scalar_one_or_none()
    if not supply:
        raise HTTPException(status_code=404, detail="Supply not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(supply, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Supply SKU already exists") from exc
    await db.refresh(supply)
    return supply


@router.post("/{supply_id}/adjust", response_model=SupplyResponse, summary="Adjust supply quantity")
async def adjust_supply(supply_id: uuid.UUID, body: SupplyAdjust, user: CurrentUser, db: DB):
    supply = (await db.execute(select(Supply).where(Supply.id == supply_id))).scalar_one_or_none()
    if not supply:
        raise HTTPException(status_code=404, detail="Supply not found")
    next_qty = supply.quantity_on_hand + body.quantity_delta
    if next_qty < 0:
        raise HTTPException(status_code=400, detail="Supply quantity cannot go below zero")
    supply.quantity_on_hand = next_qty
    await db.commit()
    await db.refresh(supply)
    return supply


@router.delete("/{supply_id}", status_code=204, summary="Archive a supply")
async def delete_supply(supply_id: uuid.UUID, user: CurrentUser, db: DB):
    supply = (await db.execute(select(Supply).where(Supply.id == supply_id))).scalar_one_or_none()
    if not supply:
        raise HTTPException(status_code=404, detail="Supply not found")
    supply.active = False
    await db.commit()
