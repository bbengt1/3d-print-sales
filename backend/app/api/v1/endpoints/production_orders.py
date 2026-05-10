from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.production_order import (
    FinishedGoodsLayer,
    ProductionOrder,
    ProductionOrderConsumption,
)
from app.services.production_order_service import (
    ProductionOrderError,
    cancel_order,
    close_order,
    create_order,
)


router = APIRouter(prefix="/production-orders", tags=["ProductionOrders"])


class POCreate(BaseModel):
    product_id: uuid.UUID
    output_quantity: Decimal = Field(..., gt=0)
    planned_start_date: date | None = None
    notes: str | None = None


class ConsumptionOut(BaseModel):
    id: uuid.UUID
    kind: str
    material_id: uuid.UUID | None
    supply_id: uuid.UUID | None
    product_id: uuid.UUID | None
    planned_qty: Decimal
    actual_qty: Decimal | None
    actual_unit_cost: Decimal | None
    actual_total_cost: Decimal | None


class POResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    product_id: uuid.UUID
    output_quantity: Decimal
    status: str
    planned_start_date: date | None
    completed_at: datetime | None
    total_material_cost: Decimal | None
    applied_overhead: Decimal | None
    total_finished_goods_value: Decimal | None
    journal_entry_id: uuid.UUID | None
    notes: str | None


class PODetail(POResponse):
    consumptions: list[ConsumptionOut]


def _to_response(order: ProductionOrder) -> POResponse:
    return POResponse(
        id=order.id,
        order_number=order.order_number,
        product_id=order.product_id,
        output_quantity=Decimal(order.output_quantity),
        status=order.status,
        planned_start_date=order.planned_start_date,
        completed_at=order.completed_at,
        total_material_cost=Decimal(order.total_material_cost) if order.total_material_cost is not None else None,
        applied_overhead=Decimal(order.applied_overhead) if order.applied_overhead is not None else None,
        total_finished_goods_value=Decimal(order.total_finished_goods_value) if order.total_finished_goods_value is not None else None,
        journal_entry_id=order.journal_entry_id,
        notes=order.notes,
    )


@router.post("", response_model=POResponse, status_code=status.HTTP_201_CREATED, summary="Create a planned production order with BOM snapshot")
async def create(body: POCreate, user: CurrentUser, db: DB):
    try:
        order = await create_order(
            db,
            product_id=body.product_id,
            output_quantity=body.output_quantity,
            planned_start_date=body.planned_start_date,
            notes=body.notes,
        )
    except ProductionOrderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(order)


@router.get("", response_model=list[POResponse], summary="List production orders")
async def list_orders(user: CurrentUser, db: DB, status_filter: str | None = None):
    stmt = select(ProductionOrder).order_by(ProductionOrder.created_at.desc())
    if status_filter:
        stmt = stmt.where(ProductionOrder.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.get("/{order_id}", response_model=PODetail, summary="Production order detail with consumption snapshot")
async def get_order(order_id: uuid.UUID, user: CurrentUser, db: DB):
    order = (await db.execute(select(ProductionOrder).where(ProductionOrder.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Production order not found")
    rows = (
        await db.execute(
            select(ProductionOrderConsumption).where(
                ProductionOrderConsumption.production_order_id == order.id
            )
        )
    ).scalars().all()
    consumptions = [
        ConsumptionOut(
            id=c.id,
            kind=c.kind,
            material_id=c.material_id,
            supply_id=c.supply_id,
            product_id=c.product_id,
            planned_qty=Decimal(c.planned_qty),
            actual_qty=Decimal(c.actual_qty) if c.actual_qty is not None else None,
            actual_unit_cost=Decimal(c.actual_unit_cost) if c.actual_unit_cost is not None else None,
            actual_total_cost=Decimal(c.actual_total_cost) if c.actual_total_cost is not None else None,
        )
        for c in rows
    ]
    return PODetail(**_to_response(order).model_dump(), consumptions=consumptions)


@router.post("/{order_id}/close", response_model=POResponse, summary="Close a planned production order — FIFO-consume materials, post JE, create finished-goods layer")
async def close_ep(order_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        order = await close_order(db, order_id)
    except ProductionOrderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(order)


@router.post("/{order_id}/cancel", response_model=POResponse, summary="Cancel a planned order (no GL impact)")
async def cancel_ep(order_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        order = await cancel_order(db, order_id)
    except ProductionOrderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(order)


# ---------- finished-goods layers (read-only) ----------


@router.get("/finished-goods/{product_id}", summary="List finished-goods layers for a product (Phase 2 will use these for COGS)")
async def list_layers(product_id: uuid.UUID, user: CurrentUser, db: DB, only_remaining: bool = True):
    stmt = select(FinishedGoodsLayer).where(FinishedGoodsLayer.product_id == product_id).order_by(FinishedGoodsLayer.created_at)
    if only_remaining:
        stmt = stmt.where(FinishedGoodsLayer.qty_remaining > 0)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "production_order_id": str(r.production_order_id) if r.production_order_id else None,
            "qty_total": str(Decimal(r.qty_total)),
            "qty_remaining": str(Decimal(r.qty_remaining)),
            "unit_cost": str(Decimal(r.unit_cost)),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
