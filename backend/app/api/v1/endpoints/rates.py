from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB
from app.models.rate import Rate

router = APIRouter(prefix="/rates", tags=["Rates"])


class RateResponse(BaseModel):
    id: uuid.UUID
    name: str
    value: Decimal
    unit: str
    notes: str | None = None
    active: bool

    model_config = {"from_attributes": True}


class RateCreate(BaseModel):
    name: str
    value: Decimal
    unit: str
    notes: str | None = None
    active: bool = True


class RateUpdate(BaseModel):
    name: str | None = None
    value: Decimal | None = None
    unit: str | None = None
    notes: str | None = None
    active: bool | None = None


@router.get("", response_model=list[RateResponse])
async def list_rates(db: DB, active: bool | None = Query(None)):
    stmt = select(Rate)
    if active is not None:
        stmt = stmt.where(Rate.active == active)
    result = await db.execute(stmt.order_by(Rate.name))
    return result.scalars().all()


@router.get("/{rate_id}", response_model=RateResponse)
async def get_rate(rate_id: uuid.UUID, db: DB):
    result = await db.execute(select(Rate).where(Rate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    return rate


@router.post("", response_model=RateResponse, status_code=201)
async def create_rate(body: RateCreate, db: DB):
    rate = Rate(**body.model_dump())
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.put("/{rate_id}", response_model=RateResponse)
async def update_rate(rate_id: uuid.UUID, body: RateUpdate, db: DB):
    result = await db.execute(select(Rate).where(Rate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rate, field, value)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.delete("/{rate_id}", status_code=204)
async def delete_rate(rate_id: uuid.UUID, db: DB):
    result = await db.execute(select(Rate).where(Rate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    rate.active = False
    await db.commit()
