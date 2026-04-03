from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, Body, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.models.approval_request import ApprovalRequest
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel
from app.models.tax_profile import TaxProfile
from app.schemas.approval import RefundRequestBody
from app.schemas.sale import (
    POSCheckoutCreate,
    PaginatedSales,
    SaleCreate,
    SaleListResponse,
    SaleResponse,
    SaleStatus,
    SaleUpdate,
    SalesMetrics,
)
from app.services.accounting_service import AccountingValidationError, assert_financial_date_editable
from app.services.audit_service import create_audit_log, snapshot_model
from app.services.sales_service import (
    compute_sale_totals,
    create_sale_with_items,
    deduct_inventory_for_sale,
    generate_sale_number,
    restore_inventory_for_refund,
)

router = APIRouter(prefix="/sales", tags=["Sales"])


def _to_sale_response(sale: Sale) -> SaleResponse:
    item_cogs = sum((item.unit_cost or Decimal(0)) * item.quantity for item in sale.items)
    gross_profit = sale.total - item_cogs
    channel = getattr(sale, "channel", None)
    return SaleResponse(
        id=sale.id,
        sale_number=sale.sale_number,
        date=sale.date,
        customer_id=sale.customer_id,
        customer_name=sale.customer_name,
        channel_id=sale.channel_id,
        channel_name=channel.name if channel else ("Direct" if sale.channel_id is None else None),
        tax_profile_id=sale.tax_profile_id,
        tax_treatment=sale.tax_treatment,
        status=sale.status,
        subtotal=sale.subtotal,
        shipping_charged=sale.shipping_charged,
        shipping_cost=sale.shipping_cost,
        platform_fees=sale.platform_fees,
        tax_collected=sale.tax_collected,
        total=sale.total,
        item_cogs=item_cogs,
        gross_profit=gross_profit,
        contribution_margin=sale.net_revenue,
        payment_method=sale.payment_method,
        tracking_number=sale.tracking_number,
        notes=sale.notes,
        items=sale.items,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
    )


@router.get(
    "",
    response_model=PaginatedSales,
    summary="List sales",
    description="Returns paginated sales with filtering by status, channel, customer, and date range.",
)
async def list_sales(
    db: DB,
    status: SaleStatus | None = Query(None, description="Filter by status"),
    channel_id: uuid.UUID | None = Query(None, description="Filter by channel"),
    payment_method: str | None = Query(None, description="Filter by payment method"),
    customer_id: uuid.UUID | None = Query(None, description="Filter by customer"),
    date_from: datetime.date | None = Query(None, description="Start date"),
    date_to: datetime.date | None = Query(None, description="End date"),
    search: str | None = Query(None, description="Search by sale number or customer name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    base = select(Sale, SalesChannel.name.label("channel_name")).outerjoin(
        SalesChannel, SalesChannel.id == Sale.channel_id
    ).where(Sale.is_deleted == False)
    if status:
        base = base.where(Sale.status == status.value)
    if channel_id:
        base = base.where(Sale.channel_id == channel_id)
    if payment_method:
        base = base.where(Sale.payment_method == payment_method)
    if customer_id:
        base = base.where(Sale.customer_id == customer_id)
    if date_from:
        base = base.where(Sale.date >= date_from)
    if date_to:
        base = base.where(Sale.date <= date_to)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            Sale.sale_number.ilike(pattern) | Sale.customer_name.ilike(pattern)
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    result = await db.execute(
        base.options(selectinload(Sale.items), selectinload(Sale.channel))
        .order_by(Sale.date.desc())
        .offset(skip)
        .limit(limit)
    )
    sales = result.all()

    items = [
        SaleListResponse(
            id=row.Sale.id,
            sale_number=row.Sale.sale_number,
            date=row.Sale.date,
            customer_name=row.Sale.customer_name,
            channel_id=row.Sale.channel_id,
            channel_name=row.channel_name or ("Direct" if row.Sale.channel_id is None else None),
            payment_method=row.Sale.payment_method,
            status=row.Sale.status,
            total=row.Sale.total,
            gross_profit=row.Sale.total - sum((item.unit_cost or Decimal(0)) * item.quantity for item in row.Sale.items),
            contribution_margin=row.Sale.net_revenue,
            item_count=len(row.Sale.items),
            created_at=row.Sale.created_at,
        )
        for row in sales
    ]

    return PaginatedSales(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/metrics",
    response_model=SalesMetrics,
    summary="Sales metrics",
    description="Aggregated sales metrics: revenue, units, AOV, refund rate, by-channel breakdown.",
)
async def get_metrics(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    channel_id: uuid.UUID | None = Query(None),
    payment_method: str | None = Query(None),
):
    base = select(Sale).where(Sale.is_deleted == False)
    if date_from:
        base = base.where(Sale.date >= date_from)
    if date_to:
        base = base.where(Sale.date <= date_to)
    if channel_id:
        base = base.where(Sale.channel_id == channel_id)
    if payment_method:
        base = base.where(Sale.payment_method == payment_method)

    result = await db.execute(base.options(selectinload(Sale.items)))
    sales = result.scalars().all()

    completed = [s for s in sales if s.status not in ("cancelled", "refunded")]
    refunded = [s for s in sales if s.status == "refunded"]

    total_revenue = sum(float(s.total) for s in completed)
    total_cost = sum(
        sum(float(i.unit_cost) * i.quantity for i in s.items)
        for s in completed
    )
    total_platform_fees = sum(float(s.platform_fees) for s in completed)
    total_shipping_costs = sum(float(s.shipping_cost) for s in completed)
    total_contribution_margin = sum(float(s.net_revenue) for s in completed)
    total_units = sum(sum(i.quantity for i in s.items) for s in completed)
    total_sales = len(completed)

    # Revenue by channel
    channel_rev: dict[uuid.UUID | None, dict[str, float]] = {}
    for s in completed:
        bucket = channel_rev.setdefault(s.channel_id, {
            "gross_sales": 0.0,
            "item_cogs": 0.0,
            "gross_profit": 0.0,
            "platform_fees": 0.0,
            "shipping_costs": 0.0,
            "contribution_margin": 0.0,
        })
        item_cogs = sum(float(i.unit_cost) * i.quantity for i in s.items)
        gross_profit = float(s.total) - item_cogs
        bucket["gross_sales"] += float(s.total)
        bucket["item_cogs"] += item_cogs
        bucket["gross_profit"] += gross_profit
        bucket["platform_fees"] += float(s.platform_fees)
        bucket["shipping_costs"] += float(s.shipping_cost)
        bucket["contribution_margin"] += float(s.net_revenue)

    # Fetch channel names
    channel_names: dict[uuid.UUID, str] = {}
    if channel_rev:
        ch_ids = [cid for cid in channel_rev if cid is not None]
        if ch_ids:
            ch_result = await db.execute(
                select(SalesChannel).where(SalesChannel.id.in_(ch_ids))
            )
            for ch in ch_result.scalars().all():
                channel_names[ch.id] = ch.name

    revenue_by_channel = [
        {
            "channel_id": str(cid) if cid else None,
            "channel_name": channel_names.get(cid, "Direct") if cid else "Direct",
            **values,
            "order_count": sum(1 for s in completed if s.channel_id == cid),
        }
        for cid, values in channel_rev.items()
    ]

    payment_method_map: dict[str, dict[str, float | int | str]] = {}
    for s in completed:
        key = (s.payment_method or "unknown").strip() or "unknown"
        bucket = payment_method_map.setdefault(
            key,
            {
                "payment_method": key,
                "order_count": 0,
                "gross_sales": 0.0,
                "contribution_margin": 0.0,
            },
        )
        bucket["order_count"] += 1
        bucket["gross_sales"] += float(s.total)
        bucket["contribution_margin"] += float(s.net_revenue)

    return SalesMetrics(
        total_sales=total_sales,
        gross_sales=total_revenue,
        item_cogs=total_cost,
        gross_profit=total_revenue - total_cost,
        platform_fees=total_platform_fees,
        shipping_costs=total_shipping_costs,
        contribution_margin=total_contribution_margin,
        net_profit=None,
        total_units_sold=total_units,
        avg_order_value=total_revenue / total_sales if total_sales > 0 else 0,
        refund_count=len(refunded),
        refund_rate=len(refunded) / len(sales) * 100 if sales else 0,
        revenue_by_channel=revenue_by_channel,
        payment_method_breakdown=sorted(
            payment_method_map.values(),
            key=lambda item: float(item["gross_sales"]),
            reverse=True,
        ),
    )


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Get sale by ID",
    description="Retrieve a sale with its line items.",
)
async def get_sale(sale_id: uuid.UUID, db: DB):
    result = await db.execute(
        select(Sale)
        .options(selectinload(Sale.items), selectinload(Sale.channel))
        .where(Sale.id == sale_id, Sale.is_deleted == False)
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return _to_sale_response(sale)


@router.post(
    "",
    response_model=SaleResponse,
    status_code=201,
    summary="Create a sale",
    description="Create a sale with line items. Platform fees are auto-computed from channel. Inventory is deducted for product items.",
)
async def create_sale(body: SaleCreate, user: CurrentUser, db: DB):
    try:
        sale = await create_sale_with_items(
            db,
            user_id=user.id,
            date=body.date,
            customer_id=body.customer_id,
            customer_name=body.customer_name,
            channel_id=body.channel_id,
            tax_profile_id=body.tax_profile_id,
            tax_treatment=body.tax_treatment,
            shipping_charged=body.shipping_charged,
            shipping_cost=body.shipping_cost,
            tax_collected=body.tax_collected,
            payment_method=body.payment_method,
            tracking_number=body.tracking_number,
            notes=body.notes,
            status=body.status.value,
            items=body.items,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await create_audit_log(
        db,
        actor_user_id=user.id,
        entity_type="sale",
        entity_id=str(sale.id),
        action="create",
        after_snapshot={
            "sale_number": sale.sale_number,
            "status": sale.status,
            "total": sale.total,
            "customer_name": sale.customer_name,
            "tax_treatment": sale.tax_treatment,
        },
        reason=body.notes,
    )
    await db.commit()

    # Re-fetch with items
    result = await db.execute(
        select(Sale).options(selectinload(Sale.items), selectinload(Sale.channel)).where(Sale.id == sale.id)
    )
    return _to_sale_response(result.scalar_one())


@router.put(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Update a sale",
    description="Update sale details (not line items). Status changes to 'refunded' restore inventory.",
)
async def update_sale(sale_id: uuid.UUID, body: SaleUpdate, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Sale)
        .options(selectinload(Sale.items))
        .where(Sale.id == sale_id, Sale.is_deleted == False)
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    try:
        await assert_financial_date_editable(db, target_date=sale.date, detail_prefix="This sale")
    except AccountingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    old_status = sale.status
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "status":
            setattr(sale, field, value.value if hasattr(value, "value") else value)
        else:
            setattr(sale, field, value)

    # Recalculate totals if channel changed
    if body.channel_id is not None or body.shipping_charged is not None or body.tax_collected is not None:
        items_data = [{"unit_price": i.unit_price, "quantity": i.quantity, "unit_cost": i.unit_cost} for i in sale.items]
        totals = await compute_sale_totals(
            db=db,
            items=items_data,
            channel_id=sale.channel_id,
            shipping_charged=sale.shipping_charged,
            shipping_cost=sale.shipping_cost,
            tax_collected=sale.tax_collected,
        )
        for k, v in totals.items():
            setattr(sale, k, v)

    # Handle refund
    if sale.status == "refunded" and old_status != "refunded":
        await restore_inventory_for_refund(db, sale, user.id)

    await db.commit()
    await db.refresh(sale)

    result = await db.execute(
        select(Sale).options(selectinload(Sale.items), selectinload(Sale.channel)).where(Sale.id == sale.id)
    )
    return _to_sale_response(result.scalar_one())


@router.delete(
    "/{sale_id}",
    status_code=204,
    summary="Delete a sale",
    description="Soft-deletes a sale.",
)
async def delete_sale(sale_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Sale).where(Sale.id == sale_id, Sale.is_deleted == False)
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    try:
        await assert_financial_date_editable(db, target_date=sale.date, detail_prefix="This sale")
    except AccountingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sale.is_deleted = True
    await db.commit()


@router.post(
    "/{sale_id}/refund",
    response_model=SaleResponse,
    summary="Refund a sale",
    description="Mark a sale as refunded and restore inventory.",
)
async def refund_sale(sale_id: uuid.UUID, body: RefundRequestBody = Body(...), user: CurrentUser = None, db: DB = None):
    result = await db.execute(
        select(Sale)
        .options(selectinload(Sale.items), selectinload(Sale.channel))
        .where(Sale.id == sale_id, Sale.is_deleted == False)
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    try:
        await assert_financial_date_editable(db, target_date=sale.date, detail_prefix="This sale")
    except AccountingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if sale.status == "refunded":
        raise HTTPException(status_code=400, detail="Sale is already refunded")
    if not body.reason:
        raise HTTPException(status_code=400, detail="Refunds require a documented reason")

    if user.role != "admin":
        request = ApprovalRequest(
            action_type="sale_refund",
            entity_type="sale",
            entity_id=str(sale.id),
            requested_by_user_id=user.id,
            reason=body.reason,
            request_payload={"sale_id": str(sale.id), "reason": body.reason},
        )
        db.add(request)
        await db.flush()
        await create_audit_log(
            db,
            actor_user_id=user.id,
            entity_type="approval_request",
            entity_id=str(request.id),
            action="request_create",
            after_snapshot={"action_type": request.action_type, "entity_type": request.entity_type, "entity_id": request.entity_id, "status": request.status},
            reason=body.reason,
        )
        await db.commit()
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"detail": "Refund submitted for approval"})

    before = snapshot_model(sale, ["status", "total", "customer_name"])
    sale.status = "refunded"
    await restore_inventory_for_refund(db, sale, user.id)
    await create_audit_log(
        db,
        actor_user_id=user.id,
        entity_type="sale",
        entity_id=str(sale.id),
        action="refund",
        before_snapshot=before,
        after_snapshot=snapshot_model(sale, ["status", "total", "customer_name"]),
        reason=body.reason,
    )
    await db.commit()

    result = await db.execute(
        select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale.id)
    )
    return _to_sale_response(result.scalar_one())
