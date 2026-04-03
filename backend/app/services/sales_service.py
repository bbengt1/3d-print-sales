from __future__ import annotations

from collections import defaultdict
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel
from app.models.product import Product
from app.models.inventory_transaction import InventoryTransaction
from app.services.inventory_accounting_service import post_cogs_for_sale


class InsufficientStockError(Exception):
    """Raised when a sale should be blocked because stock is insufficient."""


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


async def get_or_create_sales_channel(
    db: AsyncSession,
    *,
    name: str,
    platform_fee_pct: Decimal = Decimal(0),
    fixed_fee: Decimal = Decimal(0),
) -> SalesChannel:
    result = await db.execute(select(SalesChannel).where(SalesChannel.name == name))
    channel = result.scalar_one_or_none()
    if channel:
        return channel

    channel = SalesChannel(
        name=name,
        platform_fee_pct=platform_fee_pct,
        fixed_fee=fixed_fee,
    )
    db.add(channel)
    await db.flush()
    return channel


async def resolve_sale_customer(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID | None,
    customer_name: str | None,
) -> tuple[uuid.UUID | None, str | None]:
    if not customer_id:
        return None, customer_name

    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise ValueError("Customer not found")

    return customer.id, customer_name or customer.name


async def validate_stock_availability_for_sale(
    db: AsyncSession,
    *,
    items: list,
) -> None:
    requested_by_product: dict[uuid.UUID, int] = defaultdict(int)
    for item in items:
        item_data = item.model_dump() if hasattr(item, "model_dump") else item
        product_id = item_data.get("product_id")
        quantity = item_data.get("quantity", 0)
        if product_id:
            requested_by_product[product_id] += quantity

    if not requested_by_product:
        return

    result = await db.execute(select(Product).where(Product.id.in_(requested_by_product.keys())))
    products = {product.id: product for product in result.scalars().all()}

    missing_product_ids = [product_id for product_id in requested_by_product if product_id not in products]
    if missing_product_ids:
        raise ValueError("Product not found")

    insufficient: list[str] = []
    for product_id, requested_qty in requested_by_product.items():
        product = products[product_id]
        if product.stock_qty < requested_qty:
            insufficient.append(
                f"{product.name} only has {product.stock_qty} in stock; requested {requested_qty}"
            )

    if insufficient:
        raise InsufficientStockError("Insufficient stock for POS checkout: " + "; ".join(insufficient))


async def create_sale_with_items(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    date,
    customer_id: uuid.UUID | None,
    customer_name: str | None,
    channel_id: uuid.UUID | None,
    tax_profile_id: uuid.UUID | None,
    tax_treatment: str,
    shipping_charged: Decimal,
    shipping_cost: Decimal,
    tax_collected: Decimal,
    payment_method: str | None,
    tracking_number: str | None,
    notes: str | None,
    status: str,
    items: list,
    enforce_stock_availability: bool = False,
) -> Sale:
    resolved_customer_id, resolved_customer_name = await resolve_sale_customer(
        db,
        customer_id=customer_id,
        customer_name=customer_name,
    )

    if enforce_stock_availability:
        await validate_stock_availability_for_sale(db, items=items)

    sale_number = await generate_sale_number(db)
    items_data = [i.model_dump() if hasattr(i, "model_dump") else i for i in items]
    totals = await compute_sale_totals(
        db=db,
        items=items_data,
        channel_id=channel_id,
        shipping_charged=shipping_charged,
        shipping_cost=shipping_cost,
        tax_collected=tax_collected,
    )

    sale = Sale(
        sale_number=sale_number,
        date=date,
        customer_id=resolved_customer_id,
        customer_name=resolved_customer_name,
        channel_id=channel_id,
        tax_profile_id=tax_profile_id,
        tax_treatment=tax_treatment,
        status=status,
        shipping_charged=shipping_charged,
        shipping_cost=shipping_cost,
        tax_collected=tax_collected,
        payment_method=payment_method,
        tracking_number=tracking_number,
        notes=notes,
        created_by=user_id,
        **totals,
    )
    db.add(sale)
    await db.flush()

    sale_items = []
    for item_data in items:
        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=item_data.product_id,
            job_id=item_data.job_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            line_total=item_data.unit_price * item_data.quantity,
            unit_cost=item_data.unit_cost,
        )
        db.add(sale_item)
        sale_items.append(sale_item)

    await deduct_inventory_for_sale(db, sale.id, sale_items, user_id)
    await db.flush()
    return sale


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
