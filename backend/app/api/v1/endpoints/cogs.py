from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.setting import Setting
from app.services.cogs_fifo_service import (
    FEATURE_FLAG_KEY,
    compute_sale_cogs,
    is_fifo_enabled,
)


router = APIRouter(prefix="/cogs", tags=["COGS"])


class FifoFlagResponse(BaseModel):
    enabled: bool


class FifoFlagUpdate(BaseModel):
    enabled: bool


@router.get(
    "/fifo-flag",
    response_model=FifoFlagResponse,
    summary="#317: Get FIFO sales-COGS feature flag",
)
async def get_fifo_flag(user: CurrentUser, db: DB):
    return FifoFlagResponse(enabled=await is_fifo_enabled(db))


@router.put(
    "/fifo-flag",
    response_model=FifoFlagResponse,
    summary="#317: Set FIFO sales-COGS feature flag (admin only)",
)
async def set_fifo_flag(body: FifoFlagUpdate, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    row = (
        await db.execute(select(Setting).where(Setting.key == FEATURE_FLAG_KEY))
    ).scalar_one_or_none()
    val = "true" if body.enabled else "false"
    if row is None:
        db.add(
            Setting(
                key=FEATURE_FLAG_KEY,
                value=val,
                notes=(
                    "Sales-side COGS draws from FinishedGoodsLayer FIFO when on. "
                    "Off = legacy snapshot-cost behavior."
                ),
            )
        )
    else:
        row.value = val
    await db.commit()
    return FifoFlagResponse(enabled=body.enabled)


class DryRunResponse(BaseModel):
    sale_id: uuid.UUID
    snapshot_cogs: Decimal
    fifo_cogs: Decimal
    fifo_from_layers: Decimal
    fifo_from_snapshot: Decimal
    variance: Decimal


@router.get(
    "/sales/{sale_id}/fifo-dry-run",
    response_model=DryRunResponse,
    summary="#317: Preview FIFO vs snapshot COGS for a sale (no mutation)",
)
async def dry_run(sale_id: uuid.UUID, user: CurrentUser, db: DB):
    sale = (await db.execute(select(Sale).where(Sale.id == sale_id))).scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    items = (
        await db.execute(select(SaleItem).where(SaleItem.sale_id == sale_id))
    ).scalars().all()
    snapshot = sum(
        Decimal(it.unit_cost or 0) * it.quantity for it in items if it.product_id
    )
    breakdown = await compute_sale_cogs(db, list(items), apply=False)
    return DryRunResponse(
        sale_id=sale_id,
        snapshot_cogs=Decimal(snapshot).quantize(Decimal("0.0001")),
        fifo_cogs=breakdown["total_cogs"],
        fifo_from_layers=breakdown["from_layers"],
        fifo_from_snapshot=breakdown["from_snapshot"],
        variance=(breakdown["total_cogs"] - Decimal(snapshot)).quantize(Decimal("0.0001")),
    )
