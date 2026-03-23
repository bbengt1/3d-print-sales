from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.inventory_transaction import InventoryTransaction
from app.models.material import Material
from app.models.product import Product
from app.schemas.product import (
    InventoryAlert,
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
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    base = select(InventoryTransaction)
    if product_id:
        base = base.where(InventoryTransaction.product_id == product_id)
    if type:
        base = base.where(InventoryTransaction.type == type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    result = await db.execute(
        base.order_by(InventoryTransaction.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()

    return PaginatedTransactions(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "/transactions",
    response_model=InventoryTransactionResponse,
    status_code=201,
    summary="Create stock adjustment",
    description="Manually adjust inventory stock. Use positive quantity to add, negative to remove.",
)
async def create_transaction(body: InventoryTransactionCreate, user: CurrentUser, db: DB):
    # Verify product exists
    result = await db.execute(select(Product).where(Product.id == body.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

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
