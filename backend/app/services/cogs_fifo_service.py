"""#317: sales-side COGS FIFO consumption.

When the feature flag `cogs.fifo_consumption_on_sale_enabled` is on,
sales draw COGS from `FinishedGoodsLayer` rows in FIFO order (oldest
created_at first). Each consumption decrements `qty_remaining` on the
source layer and produces a `ProductSaleConsumption` audit row.

When a product has no remaining layers (or the flag is off) we fall
back to the SaleItem's snapshot `unit_cost`, matching pre-rewrite
behavior. The fallback path is also used for kits-without-layers and
miscellaneous one-off sales that were never produced via a production
order.

This is high-blast-radius accounting code. The flag is checked at the
boundary so legacy installations stay on the old `unit_cost × qty`
COGS computation until an operator opts in. After enabling, run
`run_fifo_dry_run(...)` to compare actual layer cost vs. the snapshot
cost — if the variance is too large, surface it before turning the
flag on for live posting.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.production_order import FinishedGoodsLayer
from app.models.sale_item import SaleItem
from app.models.setting import Setting


FEATURE_FLAG_KEY = "cogs.fifo_consumption_on_sale_enabled"


@dataclass
class LayerDraw:
    layer_id: uuid.UUID
    quantity: Decimal
    unit_cost: Decimal

    @property
    def cost(self) -> Decimal:
        return (self.quantity * self.unit_cost).quantize(Decimal("0.0001"))


@dataclass
class ConsumptionResult:
    product_id: uuid.UUID
    quantity_requested: Decimal
    quantity_drawn_from_layers: Decimal
    quantity_uncovered: Decimal  # quantity that fell through to the snapshot fallback
    layer_draws: list[LayerDraw] = field(default_factory=list)
    layer_cost_total: Decimal = Decimal("0")

    @property
    def fully_covered(self) -> bool:
        return self.quantity_uncovered == 0


async def is_fifo_enabled(db: AsyncSession) -> bool:
    row = (
        await db.execute(select(Setting).where(Setting.key == FEATURE_FLAG_KEY))
    ).scalar_one_or_none()
    if row is None:
        return False
    return (row.value or "").strip().lower() in {"1", "true", "yes", "on"}


async def consume_finished_goods_layers(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    quantity: Decimal,
    apply: bool = True,
) -> ConsumptionResult:
    """Walk FinishedGoodsLayer rows for `product_id` in FIFO order, draw
    `quantity` units. When `apply=True` (default) the layer rows are
    mutated; when False this is a dry-run that returns what would happen.

    Returns a ConsumptionResult; the caller decides what to do with the
    `quantity_uncovered` portion (typically, post the remainder at
    snapshot cost).
    """
    qty_remaining = Decimal(quantity)
    if qty_remaining <= 0:
        return ConsumptionResult(
            product_id=product_id,
            quantity_requested=Decimal(quantity),
            quantity_drawn_from_layers=Decimal(0),
            quantity_uncovered=Decimal(0),
        )

    layers = (
        await db.execute(
            select(FinishedGoodsLayer)
            .where(
                FinishedGoodsLayer.product_id == product_id,
                FinishedGoodsLayer.qty_remaining > 0,
            )
            .order_by(FinishedGoodsLayer.created_at.asc())
        )
    ).scalars().all()

    draws: list[LayerDraw] = []
    drawn_total = Decimal(0)
    cost_total = Decimal(0)
    for layer in layers:
        if qty_remaining <= 0:
            break
        available = Decimal(layer.qty_remaining)
        take = min(available, qty_remaining)
        if take <= 0:
            continue
        draws.append(LayerDraw(layer_id=layer.id, quantity=take, unit_cost=Decimal(layer.unit_cost)))
        cost_total += take * Decimal(layer.unit_cost)
        if apply:
            layer.qty_remaining = available - take
        drawn_total += take
        qty_remaining -= take

    if apply:
        await db.flush()

    return ConsumptionResult(
        product_id=product_id,
        quantity_requested=Decimal(quantity),
        quantity_drawn_from_layers=drawn_total,
        quantity_uncovered=qty_remaining,
        layer_draws=draws,
        layer_cost_total=cost_total.quantize(Decimal("0.0001")),
    )


async def compute_sale_cogs(
    db: AsyncSession,
    items: list[SaleItem],
    *,
    apply: bool = True,
) -> dict:
    """Aggregate COGS for a sale across its product items. Returns a dict:

      {
        "total_cogs": Decimal,                # what to post Dr COGS / Cr Inventory
        "from_layers": Decimal,               # portion drawn from FIFO layers
        "from_snapshot": Decimal,             # portion fallen back to item.unit_cost
        "results": list[ConsumptionResult],   # per-item detail
      }

    Items with no `product_id` post nothing (descriptive sales). Items
    with `product_id` but no remaining layers fall back entirely to
    snapshot cost.
    """
    total = Decimal(0)
    from_layers = Decimal(0)
    from_snapshot = Decimal(0)
    results: list[ConsumptionResult] = []
    for item in items:
        if not item.product_id:
            continue
        consumption = await consume_finished_goods_layers(
            db, product_id=item.product_id, quantity=Decimal(item.quantity), apply=apply,
        )
        results.append(consumption)
        from_layers += consumption.layer_cost_total
        if consumption.quantity_uncovered > 0:
            snapshot_cost = Decimal(item.unit_cost or 0) * consumption.quantity_uncovered
            from_snapshot += snapshot_cost
        total = from_layers + from_snapshot
    return {
        "total_cogs": total.quantize(Decimal("0.0001")),
        "from_layers": from_layers.quantize(Decimal("0.0001")),
        "from_snapshot": from_snapshot.quantize(Decimal("0.0001")),
        "results": results,
    }
