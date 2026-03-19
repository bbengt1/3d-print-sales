from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.rate import Rate
from app.schemas.rate import RateCreate, RateResponse, RateUpdate

router = APIRouter(prefix="/rates", tags=["Rates"])


@router.get(
    "",
    response_model=list[RateResponse],
    summary="List rates",
    description="Returns business rates (labor, machine, overhead) with optional filtering by active status. Supports pagination.",
)
async def list_rates(
    db: DB,
    active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    stmt = select(Rate)
    if active is not None:
        stmt = stmt.where(Rate.active == active)
    result = await db.execute(stmt.order_by(Rate.name).offset(skip).limit(limit))
    return result.scalars().all()


@router.get(
    "/{rate_id}",
    response_model=RateResponse,
    summary="Get rate by ID",
    description="Retrieve a single business rate.",
)
async def get_rate(rate_id: uuid.UUID, db: DB):
    result = await db.execute(select(Rate).where(Rate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    return rate


@router.post(
    "",
    response_model=RateResponse,
    status_code=201,
    summary="Create a rate",
    description="Add a new business rate (e.g. labor rate, machine rate, overhead percentage).",
)
async def create_rate(body: RateCreate, user: CurrentUser, db: DB):
    rate = Rate(**body.model_dump())
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.put(
    "/{rate_id}",
    response_model=RateResponse,
    summary="Update a rate",
    description="Update one or more fields of a business rate.",
)
async def update_rate(rate_id: uuid.UUID, body: RateUpdate, user: CurrentUser, db: DB):
    result = await db.execute(select(Rate).where(Rate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rate, field, value)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.delete(
    "/{rate_id}",
    status_code=204,
    summary="Deactivate a rate",
    description="Soft-deletes a rate by setting active=false.",
)
async def delete_rate(rate_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(Rate).where(Rate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    rate.active = False
    await db.commit()
