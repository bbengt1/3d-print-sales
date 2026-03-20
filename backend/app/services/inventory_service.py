from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_transaction import InventoryTransaction
from app.models.material import Material
from app.models.product import Product


async def generate_sku(db: AsyncSession, material_id: uuid.UUID) -> str:
    """Generate a unique SKU in format PRD-{MATERIAL}-{NNNN}."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    material_code = material.name.upper()[:4] if material else "UNKN"

    # Find next sequence number for this material prefix
    prefix = f"PRD-{material_code}-"
    result = await db.execute(
        select(func.count()).select_from(Product).where(Product.sku.like(f"{prefix}%"))
    )
    count = result.scalar() or 0
    seq = count + 1

    return f"{prefix}{seq:04d}"


async def add_inventory_from_job(
    db: AsyncSession,
    product_id: uuid.UUID,
    job_id: uuid.UUID,
    quantity: int,
    unit_cost: Decimal,
    user_id: uuid.UUID | None = None,
) -> InventoryTransaction:
    """Create a production transaction and update product stock."""
    txn = InventoryTransaction(
        product_id=product_id,
        job_id=job_id,
        type="production",
        quantity=quantity,
        unit_cost=unit_cost,
        notes=f"Auto-added from completed job",
        created_by=user_id,
    )
    db.add(txn)

    # Update product stock and rolling average cost
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product:
        old_total_cost = product.unit_cost * product.stock_qty
        new_total_cost = unit_cost * quantity
        new_qty = product.stock_qty + quantity
        if new_qty > 0:
            product.unit_cost = (old_total_cost + new_total_cost) / new_qty
        product.stock_qty = new_qty

    return txn


async def adjust_stock(
    db: AsyncSession,
    product_id: uuid.UUID,
    txn_type: str,
    quantity: int,
    unit_cost: Decimal = Decimal(0),
    notes: str | None = None,
    user_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> InventoryTransaction:
    """Create an inventory transaction and update product stock."""
    txn = InventoryTransaction(
        product_id=product_id,
        job_id=job_id,
        type=txn_type,
        quantity=quantity,
        unit_cost=unit_cost,
        notes=notes,
        created_by=user_id,
    )
    db.add(txn)

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product:
        product.stock_qty = max(0, product.stock_qty + quantity)

    return txn
