from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_transaction import InventoryTransaction
from app.models.job import Job
from app.models.material import Material
from app.models.product import Product
from app.services.inventory_accounting_service import post_finished_goods_from_job


_SKU_SUFFIX_RE = re.compile(r"-(\d+)$")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")


def _material_sku_code(name: str | None) -> str:
    """Derive a 4-character upper-alphanumeric code from a material name.

    Whitespace, punctuation, and other non-alphanumeric characters are
    stripped before truncation so a material called "SM Spool" doesn't
    leak a space into the SKU prefix (which then broke `LIKE` matching
    and collided once the count-based numbering walked into an existing
    row — see the 2026-05-12 prod 500).
    """
    if not name:
        return "UNKN"
    cleaned = _NON_ALNUM_RE.sub("", name.upper())
    return cleaned[:4] if cleaned else "UNKN"


async def generate_sku(db: AsyncSession, material_id: uuid.UUID) -> str:
    """Generate a unique SKU in format `PRD-{MATERIAL}-{NNNN}`.

    Picks the next sequence by reading the MAX of existing suffixes
    within the prefix (not `COUNT`), so gaps from deleted or
    out-of-order inserts can't drive a collision. The caller still has
    to handle the genuine concurrent-insert race — `db.commit()` will
    raise `IntegrityError` on the unique SKU index — but in practice
    product creation is operator-driven and serial.
    """
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    material_code = _material_sku_code(material.name if material else None)

    prefix = f"PRD-{material_code}-"
    existing = (
        await db.execute(select(Product.sku).where(Product.sku.like(f"{prefix}%")))
    ).scalars().all()

    max_seq = 0
    for sku in existing:
        m = _SKU_SUFFIX_RE.search(sku)
        if m is not None:
            try:
                max_seq = max(max_seq, int(m.group(1)))
            except ValueError:
                continue

    return f"{prefix}{max_seq + 1:04d}"


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

    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job:
        await post_finished_goods_from_job(db, job)

    return txn


async def record_scrap_inventory(
    db: AsyncSession,
    *,
    product: Product,
    quantity: int,
    event_type: str,
    reason: str,
    notes: str | None = None,
    unit_cost: Decimal | None = None,
    user_id: uuid.UUID | None = None,
) -> InventoryTransaction:
    if quantity <= 0:
        raise ValueError("Scrap quantity must be greater than zero.")
    if event_type not in {"scrap", "failed_print", "writeoff", "rework"}:
        raise ValueError("Unsupported scrap event type.")

    resolved_cost = unit_cost if unit_cost is not None else product.unit_cost
    txn = InventoryTransaction(
        product_id=product.id,
        type=event_type,
        quantity=-quantity,
        unit_cost=resolved_cost,
        notes=f"{reason}" + (f" | {notes}" if notes else ""),
        created_by=user_id,
    )
    db.add(txn)
    product.stock_qty = max(0, product.stock_qty - quantity)
    await db.commit()
    await db.refresh(txn)
    await db.refresh(product)
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
