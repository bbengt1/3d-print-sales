from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.services.reference_number_service import next_number


router = APIRouter(tags=["Orders"])


# ---------- shared schemas ----------


class LineIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)


# ---------- sales orders ----------


class SOCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200)
    quote_id: uuid.UUID | None = None
    issue_date: date
    expected_ship_date: date | None = None
    notes: str | None = None
    lines: list[LineIn] = Field(..., min_length=1)


def _so_to_dict(so: SalesOrder) -> dict:
    return {
        "id": str(so.id),
        "sales_order_number": so.sales_order_number,
        "customer_id": str(so.customer_id) if so.customer_id else None,
        "customer_name": so.customer_name,
        "quote_id": str(so.quote_id) if so.quote_id else None,
        "issue_date": so.issue_date.isoformat(),
        "expected_ship_date": so.expected_ship_date.isoformat() if so.expected_ship_date else None,
        "status": so.status,
        "subtotal_amount": str(Decimal(so.subtotal_amount)),
        "total_amount": str(Decimal(so.total_amount)),
        "notes": so.notes,
    }


@router.post("/sales-orders", status_code=status.HTTP_201_CREATED, summary="Create a sales order")
async def create_so(body: SOCreate, user: CurrentUser, db: DB):
    if not body.customer_id and not body.customer_name:
        raise HTTPException(status_code=400, detail="customer_id or customer_name required")
    number = await next_number(db, "sales_order")
    so = SalesOrder(
        sales_order_number=number,
        customer_id=body.customer_id,
        customer_name=body.customer_name,
        quote_id=body.quote_id,
        issue_date=body.issue_date,
        expected_ship_date=body.expected_ship_date,
        notes=body.notes,
    )
    db.add(so)
    await db.flush()
    subtotal = Decimal("0")
    for line in body.lines:
        total = (line.quantity * line.unit_price).quantize(Decimal("0.01"))
        subtotal += total
        db.add(
            SalesOrderLine(
                sales_order_id=so.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=total,
            )
        )
    so.subtotal_amount = subtotal
    so.total_amount = subtotal
    await db.commit()
    return _so_to_dict(so)


@router.get("/sales-orders", summary="List sales orders")
async def list_so(user: CurrentUser, db: DB, customer_id: uuid.UUID | None = None, status_filter: str | None = None):
    stmt = select(SalesOrder).order_by(SalesOrder.issue_date.desc())
    if customer_id:
        stmt = stmt.where(SalesOrder.customer_id == customer_id)
    if status_filter:
        stmt = stmt.where(SalesOrder.status == status_filter)
    return [_so_to_dict(r) for r in (await db.execute(stmt)).scalars().all()]


@router.get("/sales-orders/{order_id}", summary="Sales order detail")
async def get_so(order_id: uuid.UUID, user: CurrentUser, db: DB):
    so = (await db.execute(select(SalesOrder).where(SalesOrder.id == order_id))).scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    lines = (await db.execute(select(SalesOrderLine).where(SalesOrderLine.sales_order_id == so.id))).scalars().all()
    return {
        **_so_to_dict(so),
        "lines": [
            {
                "id": str(l.id),
                "description": l.description,
                "quantity": str(Decimal(l.quantity)),
                "unit_price": str(Decimal(l.unit_price)),
                "line_total": str(Decimal(l.line_total)),
            }
            for l in lines
        ],
    }


@router.post("/sales-orders/{order_id}/confirm", summary="Confirm a draft sales order")
async def confirm_so(order_id: uuid.UUID, user: CurrentUser, db: DB):
    so = (await db.execute(select(SalesOrder).where(SalesOrder.id == order_id))).scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot confirm in status {so.status}")
    so.status = "confirmed"
    await db.commit()
    return _so_to_dict(so)


@router.post("/sales-orders/{order_id}/cancel", summary="Cancel a sales order")
async def cancel_so(order_id: uuid.UUID, user: CurrentUser, db: DB):
    so = (await db.execute(select(SalesOrder).where(SalesOrder.id == order_id))).scalar_one_or_none()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status == "cancelled":
        return _so_to_dict(so)
    so.status = "cancelled"
    await db.commit()
    return _so_to_dict(so)


# ---------- purchase orders ----------


class POCreate(BaseModel):
    vendor_id: uuid.UUID
    issue_date: date
    expected_receive_date: date | None = None
    notes: str | None = None
    lines: list[LineIn] = Field(..., min_length=1)


def _po_to_dict(po: PurchaseOrder) -> dict:
    return {
        "id": str(po.id),
        "purchase_order_number": po.purchase_order_number,
        "vendor_id": str(po.vendor_id),
        "issue_date": po.issue_date.isoformat(),
        "expected_receive_date": po.expected_receive_date.isoformat() if po.expected_receive_date else None,
        "status": po.status,
        "subtotal_amount": str(Decimal(po.subtotal_amount)),
        "total_amount": str(Decimal(po.total_amount)),
        "notes": po.notes,
    }


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED, summary="Create a purchase order")
async def create_po(body: POCreate, user: CurrentUser, db: DB):
    number = await next_number(db, "purchase_order")
    po = PurchaseOrder(
        purchase_order_number=number,
        vendor_id=body.vendor_id,
        issue_date=body.issue_date,
        expected_receive_date=body.expected_receive_date,
        notes=body.notes,
    )
    db.add(po)
    await db.flush()
    subtotal = Decimal("0")
    for line in body.lines:
        total = (line.quantity * line.unit_price).quantize(Decimal("0.01"))
        subtotal += total
        db.add(
            PurchaseOrderLine(
                purchase_order_id=po.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=total,
            )
        )
    po.subtotal_amount = subtotal
    po.total_amount = subtotal
    await db.commit()
    return _po_to_dict(po)


@router.get("/purchase-orders", summary="List purchase orders")
async def list_po(user: CurrentUser, db: DB, vendor_id: uuid.UUID | None = None, status_filter: str | None = None):
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.issue_date.desc())
    if vendor_id:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    if status_filter:
        stmt = stmt.where(PurchaseOrder.status == status_filter)
    return [_po_to_dict(r) for r in (await db.execute(stmt)).scalars().all()]


@router.get("/purchase-orders/{order_id}", summary="Purchase order detail")
async def get_po(order_id: uuid.UUID, user: CurrentUser, db: DB):
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id))).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    lines = (await db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id))).scalars().all()
    return {
        **_po_to_dict(po),
        "lines": [
            {
                "id": str(l.id),
                "description": l.description,
                "quantity": str(Decimal(l.quantity)),
                "unit_price": str(Decimal(l.unit_price)),
                "line_total": str(Decimal(l.line_total)),
            }
            for l in lines
        ],
    }


@router.post("/purchase-orders/{order_id}/confirm", summary="Confirm a draft purchase order")
async def confirm_po(order_id: uuid.UUID, user: CurrentUser, db: DB):
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id))).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot confirm in status {po.status}")
    po.status = "confirmed"
    await db.commit()
    return _po_to_dict(po)


@router.post("/purchase-orders/{order_id}/cancel", summary="Cancel a purchase order")
async def cancel_po(order_id: uuid.UUID, user: CurrentUser, db: DB):
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id))).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status == "cancelled":
        return _po_to_dict(po)
    po.status = "cancelled"
    await db.commit()
    return _po_to_dict(po)
