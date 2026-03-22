from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.schemas.material_receipt import MaterialReceiptCreate


async def create_material_receipt(
    db: AsyncSession,
    *,
    material: Material,
    payload: MaterialReceiptCreate,
) -> MaterialReceipt:
    landed_cost_per_g = (payload.landed_cost_total / payload.quantity_purchased_g) if payload.quantity_purchased_g > 0 else Decimal("0")
    total_cost = (payload.unit_cost_per_g * payload.quantity_purchased_g) + payload.landed_cost_total

    receipt = MaterialReceipt(
        material_id=material.id,
        vendor_name=payload.vendor_name,
        purchase_date=payload.purchase_date,
        receipt_number=payload.receipt_number,
        quantity_purchased_g=payload.quantity_purchased_g,
        quantity_remaining_g=payload.quantity_purchased_g,
        unit_cost_per_g=payload.unit_cost_per_g,
        landed_cost_total=payload.landed_cost_total,
        landed_cost_per_g=landed_cost_per_g,
        total_cost=total_cost,
        valuation_method=payload.valuation_method,
        notes=payload.notes,
    )
    db.add(receipt)

    # keep the material's current cost basis grounded in receipt data
    all_receipts_stmt = select(
        func.coalesce(func.sum(MaterialReceipt.total_cost), 0),
        func.coalesce(func.sum(MaterialReceipt.quantity_purchased_g), 0),
    ).where(MaterialReceipt.material_id == material.id)
    current_total_cost, current_total_qty = (await db.execute(all_receipts_stmt)).one()
    new_total_cost = Decimal(current_total_cost) + total_cost
    new_total_qty = Decimal(current_total_qty) + payload.quantity_purchased_g
    if new_total_qty > 0:
        material.cost_per_g = new_total_cost / new_total_qty
        material.spool_price = total_cost
        material.net_usable_g = payload.quantity_purchased_g
        material.spool_weight_g = payload.quantity_purchased_g
        material.spools_in_stock = max(material.spools_in_stock, 1)

    await db.commit()
    await db.refresh(receipt)
    await db.refresh(material)
    return receipt
