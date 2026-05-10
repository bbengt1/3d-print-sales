"""Production order lifecycle (#242 Phase 1).

Lifecycle: planned → completed (or cancelled).

`create_order` snapshots the product's BOM into ProductionOrderConsumption
rows so later BOM edits don't retroactively change historical orders.

`close_order`:
1. For each material consumption row, FIFO-draws from
   `material_receipts.quantity_remaining_g` exactly like the existing
   `inventory_accounting_service.consume_material_receipts_for_job`,
   capturing actual unit cost.
2. Posts JE — Cr Material Inventory (1200) for total material cost,
   Dr Finished Goods Inventory (1400) for total finished-goods value.
3. Creates one `FinishedGoodsLayer` row at unit_cost = total / output_qty.

Phase 1 deliberate cuts:
- No COGS-on-sale rewrite. Layers are recorded but `cost_calculator.py`
  remains the source of truth for sale-line cost.
- No supply consumption FIFO (snapshotted only).
- No hourly overhead (overhead is always 0; setting deferred).
- No operator-editable consumption (uses planned_qty as-is).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.material_receipt import MaterialReceipt
from app.models.product_bom_item import ProductBOMItem
from app.models.production_order import (
    FinishedGoodsLayer,
    ProductionOrder,
    ProductionOrderConsumption,
)
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
)
from app.services.reference_number_service import next_number


class ProductionOrderError(RuntimeError):
    pass


async def _account_by_code(db: AsyncSession, code: str) -> Account:
    a = (await db.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
    if a is None:
        raise ProductionOrderError(f"COA missing account code {code}; run migration")
    return a


async def create_order(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    output_quantity: Decimal,
    planned_start_date: date | None = None,
    notes: str | None = None,
) -> ProductionOrder:
    if output_quantity <= 0:
        raise ProductionOrderError("output_quantity must be > 0")

    bom_items = (
        await db.execute(
            select(ProductBOMItem).where(ProductBOMItem.product_id == product_id)
        )
    ).scalars().all()

    number = await next_number(db, "production_order")
    order = ProductionOrder(
        order_number=number,
        product_id=product_id,
        output_quantity=Decimal(output_quantity),
        status="planned",
        planned_start_date=planned_start_date,
        notes=notes,
    )
    db.add(order)
    await db.flush()

    # Snapshot BOM at create time. Per-piece quantity × output_quantity
    # = planned consumption.
    for item in bom_items:
        per_piece = Decimal(item.quantity)
        planned = (per_piece * Decimal(output_quantity)).quantize(Decimal("0.0001"))
        kind = item.component_type
        db.add(
            ProductionOrderConsumption(
                production_order_id=order.id,
                kind=kind,
                material_id=item.material_id if kind == "material" else None,
                supply_id=item.supply_id if kind == "supply" else None,
                product_id=item.component_product_id if kind == "product" else None,
                planned_qty=planned,
            )
        )
    await db.flush()
    return order


async def close_order(db: AsyncSession, order_id: uuid.UUID) -> ProductionOrder:
    # #293 Codex P1: serialize concurrent /close requests so two callers
    # cannot both pass the `status == "planned"` guard and each consume
    # receipts + post their own JE/finished-goods layer. `with_for_update`
    # takes a row-level lock for the duration of the surrounding
    # transaction; on databases without row locks (SQLite in tests) it is
    # silently a no-op, which is acceptable since SQLite serializes writes
    # at the file level anyway.
    order = (
        await db.execute(
            select(ProductionOrder)
            .where(ProductionOrder.id == order_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if order is None:
        raise ProductionOrderError("Production order not found")
    if order.status != "planned":
        raise ProductionOrderError(f"Cannot close production order in status {order.status}")

    consumptions = (
        await db.execute(
            select(ProductionOrderConsumption).where(
                ProductionOrderConsumption.production_order_id == order.id
            )
        )
    ).scalars().all()

    # Phase 1: only material kinds drive FIFO consumption + cost.
    total_material_cost = Decimal("0")
    for c in consumptions:
        actual_qty = Decimal(c.planned_qty)
        c.actual_qty = actual_qty
        if c.kind != "material" or c.material_id is None:
            c.actual_unit_cost = Decimal("0")
            c.actual_total_cost = Decimal("0")
            continue
        cost = await _consume_material_fifo(db, c.material_id, actual_qty)
        c.actual_total_cost = cost
        c.actual_unit_cost = (cost / actual_qty).quantize(Decimal("0.000001")) if actual_qty > 0 else Decimal("0")
        total_material_cost += cost

    applied_overhead = Decimal("0")  # Phase 1: no overhead rate
    total_value = total_material_cost + applied_overhead
    unit_cost = (
        (total_value / Decimal(order.output_quantity)).quantize(Decimal("0.000001"))
        if order.output_quantity > 0
        else Decimal("0")
    )

    # Post JE: Cr Material Inventory / Dr Finished Goods Inventory.
    #
    # #293 Codex P1: pass `commit=False` so the JE write does NOT commit
    # mid-close. The surrounding endpoint commits once at the end, so the
    # JE, the order's status/completed_at update, and the finished-goods
    # layer insert all live in a single transaction — if any step below
    # raises, the JE rolls back with the rest instead of leaving books
    # mutated while the order remains 'planned'.
    if total_value > 0:
        material_inv = await _account_by_code(db, "1200")  # Raw Materials Inventory
        finished_goods = await _account_by_code(db, "1400")  # Finished Goods Inventory
        try:
            entry = await create_journal_entry(
                db,
                JournalEntryCreate(
                    entry_date=datetime.now(timezone.utc).date(),
                    source_type="production_order",
                    source_id=str(order.id),
                    memo=f"Close production order {order.order_number}",
                    lines=[
                        JournalLineCreate(
                            account_id=finished_goods.id,
                            entry_type="debit",
                            amount=total_value,
                            description=f"Finished goods from {order.order_number}",
                        ),
                        JournalLineCreate(
                            account_id=material_inv.id,
                            entry_type="credit",
                            amount=total_value,
                            description=f"Material consumption for {order.order_number}",
                        ),
                    ],
                ),
                commit=False,
            )
        except AccountingValidationError as e:
            raise ProductionOrderError(str(e)) from e
        order.journal_entry_id = entry.id

    # Create finished-goods layer
    db.add(
        FinishedGoodsLayer(
            product_id=order.product_id,
            production_order_id=order.id,
            qty_total=Decimal(order.output_quantity),
            qty_remaining=Decimal(order.output_quantity),
            unit_cost=unit_cost,
        )
    )

    order.status = "completed"
    order.completed_at = datetime.now(timezone.utc)
    order.total_material_cost = total_material_cost
    order.applied_overhead = applied_overhead
    order.total_finished_goods_value = total_value
    await db.flush()
    return order


async def cancel_order(db: AsyncSession, order_id: uuid.UUID) -> ProductionOrder:
    order = (await db.execute(select(ProductionOrder).where(ProductionOrder.id == order_id))).scalar_one_or_none()
    if order is None:
        raise ProductionOrderError("Production order not found")
    if order.status == "cancelled":
        return order
    if order.status == "completed":
        raise ProductionOrderError("Cannot cancel a completed production order")
    order.status = "cancelled"
    await db.flush()
    return order


async def _consume_material_fifo(
    db: AsyncSession, material_id: uuid.UUID, qty: Decimal
) -> Decimal:
    """FIFO consume `qty` from material_receipts and return total cost.

    Mirrors `inventory_accounting_service.consume_material_receipts_for_job`.
    Uses the receipt's `landed_cost_per_g` when populated, falling back to
    `unit_cost_per_g`.
    """
    if qty <= 0:
        return Decimal("0")

    receipts = (
        await db.execute(
            select(MaterialReceipt)
            .where(
                MaterialReceipt.material_id == material_id,
                MaterialReceipt.quantity_remaining_g > 0,
            )
            .order_by(MaterialReceipt.purchase_date.asc(), MaterialReceipt.created_at.asc())
        )
    ).scalars().all()

    remaining = Decimal(qty)
    cost = Decimal("0")
    for r in receipts:
        if remaining <= 0:
            break
        available = Decimal(r.quantity_remaining_g)
        consume = min(available, remaining)
        # Prefer landed cost if set, else unit cost
        per_g = Decimal(r.landed_cost_per_g) if r.landed_cost_per_g else Decimal(r.unit_cost_per_g)
        cost += (consume * per_g).quantize(Decimal("0.0001"))
        r.quantity_remaining_g = available - consume
        remaining -= consume
    # If we ran out of receipts, leave `cost` reflecting only what was
    # available. Operator can post a starting-balances adjustment if
    # they're not seeded; we don't error here so close-out remains useful
    # in light/test data.
    return cost
