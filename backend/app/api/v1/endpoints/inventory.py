from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser
from app.models.approval_request import ApprovalRequest
from app.models.inventory_transaction import InventoryTransaction
from app.models.material import Material
from app.models.product import Product
from app.schemas.product import (
    InventoryAlert,
    InventoryReconcileRequest,
    InventoryReconcileResponse,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
    PaginatedTransactions,
)
from app.services.audit_service import create_audit_log, snapshot_model
from app.services.inventory_service import adjust_stock

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get(
    "/transactions",
    response_model=PaginatedTransactions,
    summary="List inventory transactions",
    description="Returns paginated inventory transactions with filtering by product, type, and date range.",
)
async def list_transactions(
    db: DB,
    product_id: uuid.UUID | None = Query(None, description="Filter by product ID"),
    type: str | None = Query(None, description="Filter by transaction type"),
    date_from: datetime.date | None = Query(None, description="Start date (inclusive)"),
    date_to: datetime.date | None = Query(None, description="End date (inclusive)"),
    search: str | None = Query(None, description="Search by product name or SKU"),
    sort_by: str = Query(
        "created_at",
        description="Sort field (allowlisted)",
        pattern="^(created_at|type|quantity|unit_cost)$",
    ),
    sort_dir: str = Query("desc", description="Sort direction", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    base = (
        select(
            InventoryTransaction,
            Product.name.label("product_name"),
            Product.sku.label("product_sku"),
        )
        .join(Product, Product.id == InventoryTransaction.product_id)
    )
    if product_id:
        base = base.where(InventoryTransaction.product_id == product_id)
    if type:
        base = base.where(InventoryTransaction.type == type)
    if date_from:
        base = base.where(func.date(InventoryTransaction.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(InventoryTransaction.created_at) <= date_to)
    if search:
        pattern = f"%{search}%"
        base = base.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    sort_column = getattr(InventoryTransaction, sort_by, InventoryTransaction.created_at)
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    result = await db.execute(base.order_by(order).offset(skip).limit(limit))
    rows = result.all()

    items = [
        InventoryTransactionResponse(
            id=row.InventoryTransaction.id,
            product_id=row.InventoryTransaction.product_id,
            product_name=row.product_name,
            product_sku=row.product_sku,
            job_id=row.InventoryTransaction.job_id,
            type=row.InventoryTransaction.type,
            quantity=row.InventoryTransaction.quantity,
            unit_cost=row.InventoryTransaction.unit_cost,
            notes=row.InventoryTransaction.notes,
            created_by=row.InventoryTransaction.created_by,
            created_at=row.InventoryTransaction.created_at,
        )
        for row in rows
    ]

    return PaginatedTransactions(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "/transactions",
    response_model=InventoryTransactionResponse,
    status_code=201,
    summary="Create stock adjustment",
    description="Manually adjust inventory stock. Use positive quantity to add, negative to remove.",
)
async def create_transaction(body: InventoryTransactionCreate, user: CurrentUser, db: DB):
    if body.type.value == "adjustment" and not body.notes:
        raise HTTPException(status_code=400, detail="Manual inventory adjustments require a documented reason")

    # Verify product exists
    result = await db.execute(select(Product).where(Product.id == body.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if body.type.value == "adjustment" and user.role != "admin":
        request = ApprovalRequest(
            action_type="inventory_adjustment",
            entity_type="product",
            entity_id=str(product.id),
            requested_by_user_id=user.id,
            reason=body.notes or "",
            request_payload={
                "product_id": str(body.product_id),
                "type": body.type.value,
                "quantity": body.quantity,
                "unit_cost": str(body.unit_cost),
                "notes": body.notes,
            },
        )
        db.add(request)
        await create_audit_log(
            db,
            actor_user_id=user.id,
            entity_type="approval_request",
            entity_id=str(request.id),
            action="request_create",
            after_snapshot={"action_type": request.action_type, "entity_type": request.entity_type, "entity_id": request.entity_id, "status": request.status},
            reason=request.reason,
        )
        await db.commit()
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"detail": "Inventory adjustment submitted for approval"})

    before = snapshot_model(product, ["stock_qty", "unit_cost", "reorder_point"])
    txn = await adjust_stock(
        db=db,
        product_id=body.product_id,
        txn_type=body.type.value,
        quantity=body.quantity,
        unit_cost=body.unit_cost,
        notes=body.notes,
        user_id=user.id,
    )
    await db.flush()
    await db.refresh(product)
    after = snapshot_model(product, ["stock_qty", "unit_cost", "reorder_point"])
    await create_audit_log(
        db,
        actor_user_id=user.id,
        entity_type="inventory_transaction",
        entity_id=str(txn.id),
        action="create",
        before_snapshot={"product_id": str(product.id), **before},
        after_snapshot={"product_id": str(product.id), "transaction_type": body.type.value, "quantity": body.quantity, **after},
        reason=body.notes,
    )
    await db.commit()
    await db.refresh(txn)
    return txn


@router.post(
    "/reconcile",
    response_model=InventoryReconcileResponse,
    status_code=200,
    summary="Reconcile inventory from physical count",
    description="Compare counted stock to current stock and create the required variance adjustment through the existing audit/approval flow.",
)
async def reconcile_inventory(body: InventoryReconcileRequest, user: CurrentUser, db: DB):
    result = await db.execute(select(Product).where(Product.id == body.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    current_qty = product.stock_qty
    variance = body.counted_qty - current_qty
    reason_text = body.reason.strip()
    combined_notes = reason_text if not body.notes else f"{reason_text} | {body.notes.strip()}"

    if variance == 0:
        return InventoryReconcileResponse(
            product_id=product.id,
            current_qty=current_qty,
            counted_qty=body.counted_qty,
            variance=0,
            approval_required=False,
            detail="No stock adjustment needed",
            transaction=None,
        )

    if user.role != "admin":
        request = ApprovalRequest(
            action_type="inventory_adjustment",
            entity_type="product",
            entity_id=str(product.id),
            requested_by_user_id=user.id,
            reason=reason_text,
            request_payload={
                "product_id": str(product.id),
                "type": "adjustment",
                "quantity": variance,
                "unit_cost": str(product.unit_cost),
                "notes": combined_notes,
                "counted_qty": body.counted_qty,
                "current_qty": current_qty,
            },
        )
        db.add(request)
        await create_audit_log(
            db,
            actor_user_id=user.id,
            entity_type="approval_request",
            entity_id=str(request.id),
            action="request_create",
            after_snapshot={"action_type": request.action_type, "entity_type": request.entity_type, "entity_id": request.entity_id, "status": request.status},
            reason=request.reason,
        )
        await db.commit()
        return InventoryReconcileResponse(
            product_id=product.id,
            current_qty=current_qty,
            counted_qty=body.counted_qty,
            variance=variance,
            approval_required=True,
            detail="Inventory reconciliation submitted for approval",
            transaction=None,
        )

    before = snapshot_model(product, ["stock_qty", "unit_cost", "reorder_point"])
    txn = await adjust_stock(
        db=db,
        product_id=product.id,
        txn_type="adjustment",
        quantity=variance,
        unit_cost=product.unit_cost,
        notes=combined_notes,
        user_id=user.id,
    )
    await db.flush()
    await db.refresh(product)
    after = snapshot_model(product, ["stock_qty", "unit_cost", "reorder_point"])
    await create_audit_log(
        db,
        actor_user_id=user.id,
        entity_type="inventory_transaction",
        entity_id=str(txn.id),
        action="create",
        before_snapshot={"product_id": str(product.id), "counted_qty": body.counted_qty, **before},
        after_snapshot={"product_id": str(product.id), "transaction_type": "adjustment", "quantity": variance, "counted_qty": body.counted_qty, **after},
        reason=combined_notes,
    )
    await db.commit()
    await db.refresh(txn)

    response_txn = InventoryTransactionResponse(
        id=txn.id,
        product_id=txn.product_id,
        product_name=product.name,
        product_sku=product.sku,
        job_id=txn.job_id,
        type=txn.type,
        quantity=txn.quantity,
        unit_cost=txn.unit_cost,
        notes=txn.notes,
        created_by=txn.created_by,
        created_at=txn.created_at,
    )
    return InventoryReconcileResponse(
        product_id=product.id,
        current_qty=current_qty,
        counted_qty=body.counted_qty,
        variance=variance,
        approval_required=False,
        detail="Inventory reconciled successfully",
        transaction=response_txn,
    )


@router.get(
    "/alerts",
    response_model=list[InventoryAlert],
    summary="Get low-stock alerts",
    description="Returns products and materials that are below their reorder points.",
)
async def get_alerts(db: DB):
    alerts: list[InventoryAlert] = []

    # Products below reorder point
    result = await db.execute(
        select(Product).where(
            Product.is_active == True,
            Product.stock_qty <= Product.reorder_point,
        )
    )
    for p in result.scalars().all():
        alerts.append(InventoryAlert(
            type="product",
            id=p.id,
            name=p.name,
            sku=p.sku,
            current_stock=p.stock_qty,
            reorder_point=p.reorder_point,
        ))

    # Materials below reorder point
    result = await db.execute(
        select(Material).where(
            Material.active == True,
            Material.spools_in_stock <= Material.reorder_point,
        )
    )
    for m in result.scalars().all():
        alerts.append(InventoryAlert(
            type="material",
            id=m.id,
            name=f"{m.name} ({m.brand})",
            sku=None,
            current_stock=m.spools_in_stock,
            reorder_point=m.reorder_point,
        ))

    return alerts
