from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.sales_channel import SalesChannel
from app.schemas.sales_channel import (
    SalesChannelCreate,
    SalesChannelResponse,
    SalesChannelUpdate,
)

router = APIRouter(prefix="/sales/channels", tags=["Sales"])


@router.get(
    "",
    response_model=list[SalesChannelResponse],
    summary="List sales channels",
    description="Returns all sales channels with optional active filter.",
)
async def list_channels(
    db: DB,
    is_active: bool | None = Query(None, description="Filter by active status"),
):
    stmt = select(SalesChannel)
    if is_active is not None:
        stmt = stmt.where(SalesChannel.is_active == is_active)
    result = await db.execute(stmt.order_by(SalesChannel.name))
    return result.scalars().all()


@router.get(
    "/{channel_id}",
    response_model=SalesChannelResponse,
    summary="Get sales channel",
)
async def get_channel(channel_id: uuid.UUID, db: DB):
    result = await db.execute(select(SalesChannel).where(SalesChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Sales channel not found")
    return channel


@router.post(
    "",
    response_model=SalesChannelResponse,
    status_code=201,
    summary="Create sales channel",
)
async def create_channel(body: SalesChannelCreate, user: CurrentUser, db: DB):
    channel = SalesChannel(**body.model_dump())
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.put(
    "/{channel_id}",
    response_model=SalesChannelResponse,
    summary="Update sales channel",
)
async def update_channel(channel_id: uuid.UUID, body: SalesChannelUpdate, user: CurrentUser, db: DB):
    result = await db.execute(select(SalesChannel).where(SalesChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Sales channel not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.delete(
    "/{channel_id}",
    status_code=204,
    summary="Deactivate sales channel",
)
async def delete_channel(channel_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(SalesChannel).where(SalesChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Sales channel not found")
    channel.is_active = False
    await db.commit()
