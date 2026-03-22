from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel
from app.models.product import Product
from app.models.inventory_transaction import InventoryTransaction
from app.services.inventory_accounting_service import post_cogs_for_sale


async def generate_sale_number(db: AsyncSession) -> str:
    """Generate a unique sale number in format S-YYYY-NNNN."""
    from datetime import date
    year = date.today().year
    prefix = f"S-{year}-"
    result = await db.execute(
        select(func.count()).select_from(Sale).where(Sale.sale_number.like(f"{prefix}%"))
    )
    count = result.scalar() or 0
    return f"{prefix}{count + 1:04d}"


async def compute_sale_totals(
    db: AsyncSession,
    items: list[dict],
    channel_id: uuid.UUID | None,
    shipping_charged: Decimal,
    shipping_cost: Decimal,
    tax_collected: Decimal,
) -> dict:
    """Compute subtotal, platform fees, total, and net revenue."""
    subtotal = sum(Decimal(str(i["unit_price"])) * i["quantity"] for i in items)

    platform_fees = Decimal(0)
    if channel_id:
        result = await db.execute(select(SalesChannel).where(SalesChannel.id == channel_id))
        channel = result.scalar_one_or_none()
        if channel:
            platform_fees = subtotal * (channel.platform_fee_pct / Decimal(100)) + channel.fixed_fee

    total = subtotal + shipping_charged + tax_collected
    total_cost = sum(Decimal(str(i.get("unit_cost", 0))) * i["quantity"] for i in items)
    net_revenue = total - platform_fees - shipping_cost - total_cost

    return {
        "subtotal": subtotal,
        "platform_fees": platform_fees,
        "total": total,
        "net_revenue": net_revenue,
    }


async def deduct_inventory_for_sale(
    db: AsyncSession,
    sale_id: uuid.UUID,
    items: list[SaleItem],
    user_id: uuid.UUID | None = None,
) -> None:
    """Deduct product stock for each sale item with a product_id."""
    for item in items:
        if not item.product_id:
            continue
        result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = result.scalar_one_or_none()
        if not product:
            continue

        txn = InventoryTransaction(
            product_id=item.product_id,
            type="sale",
            quantity=-item.quantity,
            unit_cost=item.unit_cost,
            notes=f"Sale {sale_id}",
            created_by=user_id,
        )
        db.add(txn)
        product.stock_qty = max(0, product.stock_qty - item.quantity)

    sale = (await db.execute(select(Sale).where(Sale.id == sale_id))).scalar_one_or_none()
    if sale:
        await post_cogs_for_sale(db, sale, items)


async def restore_inventory_for_refund(
    db: AsyncSession,
    sale: Sale,
    user_id: uuid.UUID | None = None,
) -> None:
    """Restore product stock when a sale is refunded."""
    for item in sale.items:
        if not item.product_id:
            continue
        result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = result.scalar_one_or_none()
        if not product:
            continue

        txn = InventoryTransaction(
            product_id=item.product_id,
            type="return",
            quantity=item.quantity,
            unit_cost=item.unit_cost,
            notes=f"Refund for sale {sale.sale_number}",
            created_by=user_id,
        )
        db.add(txn)
        product.stock_qty += item.quantity
