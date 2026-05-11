"""Per-(product, location) on-hand quantity service (#318 Phase 2).

`ProductLocationStock` is the source of truth for "which location holds
how many of which product." `Product.stock_qty` is kept in sync as the
aggregate sum for backward compatibility with existing read paths.

Allocation rules
----------------
- Transfer **ship**: source on-hand drops immediately (items are now in
  transit and count as zero on-hand at the source).
- Transfer **receive**: destination on-hand rises.
- Transfer **cancel** while ``in_transit``: source on-hand is restored.
- Transfer **cancel** while ``pending``: no-op (no decrement yet).
- Sale fulfillment: the resolved location's on-hand drops.
- Refund / cancel of a sale: the original fulfillment location's on-hand
  is restored.

Negative-stock policy
---------------------
Soft-warn is the default — fulfillment is allowed and the caller can
surface the warning. Operators can flip ``inventory.prevent_negative_stock``
to ``"true"`` to make the same condition a hard block. Both branches are
evaluated against *projected* on-hand (the new value after the proposed
decrement).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_location import (
    InventoryLocation,
    InventoryTransfer,
    InventoryTransferLine,
    ProductLocationStock,
)
from app.models.product import Product
from app.models.setting import Setting


PREVENT_NEGATIVE_STOCK_KEY = "inventory.prevent_negative_stock"
DEFAULT_FULFILLMENT_KEY = "inventory.default_fulfillment_location_id"


class NegativeStockBlockedError(Exception):
    """Raised when a decrement would drive on-hand negative and the
    `inventory.prevent_negative_stock` setting is enabled."""


@dataclass
class StockWarning:
    product_id: uuid.UUID
    location_id: uuid.UUID
    requested_qty: Decimal
    projected_on_hand: Decimal


# ---------- helpers ----------


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    row = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    return row.value if row else None


async def _hard_block_enabled(db: AsyncSession) -> bool:
    val = await _get_setting(db, PREVENT_NEGATIVE_STOCK_KEY)
    return (val or "").strip().lower() == "true"


async def _ensure_default_location(db: AsyncSession) -> InventoryLocation:
    row = (
        await db.execute(select(InventoryLocation).where(InventoryLocation.name == "Default"))
    ).scalar_one_or_none()
    if row:
        return row
    row = InventoryLocation(name="Default", kind="internal")
    db.add(row)
    await db.flush()
    return row


async def resolve_fulfillment_location_id(
    db: AsyncSession, *, sale_fulfillment_location_id: uuid.UUID | None
) -> uuid.UUID:
    """Pick the location to fulfill a sale from.

    Order: explicit sale.fulfillment_location_id → setting default → the
    auto-seeded ``Default`` location. Always returns a usable id so
    callers never need to special-case None.
    """
    if sale_fulfillment_location_id:
        return sale_fulfillment_location_id

    setting_val = await _get_setting(db, DEFAULT_FULFILLMENT_KEY)
    if setting_val:
        try:
            return uuid.UUID(setting_val)
        except ValueError:
            pass

    return (await _ensure_default_location(db)).id


# ---------- read ----------


async def get_row(
    db: AsyncSession, *, product_id: uuid.UUID, location_id: uuid.UUID
) -> ProductLocationStock | None:
    return (
        await db.execute(
            select(ProductLocationStock).where(
                ProductLocationStock.product_id == product_id,
                ProductLocationStock.location_id == location_id,
            )
        )
    ).scalar_one_or_none()


async def get_on_hand(
    db: AsyncSession, *, product_id: uuid.UUID, location_id: uuid.UUID
) -> Decimal:
    row = await get_row(db, product_id=product_id, location_id=location_id)
    return Decimal(row.on_hand_qty) if row else Decimal(0)


async def in_transit_to(
    db: AsyncSession, *, product_id: uuid.UUID, location_id: uuid.UUID
) -> Decimal:
    """Sum of `in_transit` transfer-line quantities arriving at this
    location for this product. Used to project a destination's "incoming"
    qty without including it in current on-hand.
    """
    total = (
        await db.execute(
            select(func.coalesce(func.sum(InventoryTransferLine.quantity), 0))
            .join(InventoryTransfer, InventoryTransfer.id == InventoryTransferLine.transfer_id)
            .where(
                InventoryTransfer.to_location_id == location_id,
                InventoryTransfer.status == "in_transit",
                InventoryTransferLine.kind == "product",
                InventoryTransferLine.product_id == product_id,
            )
        )
    ).scalar() or 0
    return Decimal(total)


async def stock_by_product_at_location(
    db: AsyncSession, *, location_id: uuid.UUID
) -> list[ProductLocationStock]:
    return (
        (
            await db.execute(
                select(ProductLocationStock).where(ProductLocationStock.location_id == location_id)
            )
        )
        .scalars()
        .all()
    )


# ---------- write ----------


async def _refresh_product_aggregate(db: AsyncSession, product_id: uuid.UUID) -> None:
    """Recompute `Product.stock_qty` as the sum of on-hand across
    locations so existing single-bucket readers keep working.
    """
    total = (
        await db.execute(
            select(func.coalesce(func.sum(ProductLocationStock.on_hand_qty), 0)).where(
                ProductLocationStock.product_id == product_id
            )
        )
    ).scalar() or 0
    product = (
        await db.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if product is None:
        return
    # `Product.stock_qty` is Integer; in-flight Decimal totals from
    # numeric columns round down to whole units, matching the existing
    # int-only semantics on the read side.
    product.stock_qty = int(Decimal(total))
    await db.flush()


async def _ensure_product_seeded(db: AsyncSession, product_id: uuid.UUID) -> None:
    """Lazy backfill of legacy single-bucket inventory.

    If a product has ``stock_qty > 0`` in the legacy column but no
    ``ProductLocationStock`` rows yet, park that on-hand at the Default
    location so the SoT can take over. Idempotent — once any row exists
    for the product, we stop. The Alembic migration does the same thing
    eagerly for existing installs; this guards test paths and any rows
    that were inserted while the migration was running.
    """
    has_row = (
        await db.execute(
            select(ProductLocationStock.id).where(
                ProductLocationStock.product_id == product_id
            ).limit(1)
        )
    ).scalar_one_or_none()
    if has_row is not None:
        return

    product = (
        await db.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if product is None or not product.stock_qty:
        return

    default_loc = await _ensure_default_location(db)
    db.add(
        ProductLocationStock(
            product_id=product_id,
            location_id=default_loc.id,
            on_hand_qty=Decimal(product.stock_qty),
        )
    )
    await db.flush()


async def adjust(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    location_id: uuid.UUID,
    delta: Decimal,
    enforce_non_negative: bool | None = None,
) -> tuple[ProductLocationStock, StockWarning | None]:
    """Apply ``delta`` (positive = receipt, negative = consumption) to
    the (product, location) row, creating it if missing.

    Returns the row plus an optional ``StockWarning`` when a negative
    decrement drives projected on-hand below zero. Callers may surface
    the warning to the operator. When ``enforce_non_negative`` is True
    (or when the global ``inventory.prevent_negative_stock`` setting is
    enabled) the same condition raises ``NegativeStockBlockedError``
    instead.
    """
    await _ensure_product_seeded(db, product_id)

    row = await get_row(db, product_id=product_id, location_id=location_id)
    if row is None:
        row = ProductLocationStock(
            product_id=product_id,
            location_id=location_id,
            on_hand_qty=Decimal(0),
        )
        db.add(row)
        await db.flush()

    current = Decimal(row.on_hand_qty)
    projected = current + Decimal(delta)

    warning: StockWarning | None = None
    if projected < 0:
        block = enforce_non_negative
        if block is None:
            block = await _hard_block_enabled(db)
        if block:
            raise NegativeStockBlockedError(
                f"Product {product_id} at location {location_id} would go to "
                f"{projected} (have {current}, requested {-delta}); "
                f"{PREVENT_NEGATIVE_STOCK_KEY} is enabled."
            )
        warning = StockWarning(
            product_id=product_id,
            location_id=location_id,
            requested_qty=Decimal(-delta) if delta < 0 else Decimal(delta),
            projected_on_hand=projected,
        )

    row.on_hand_qty = projected
    await db.flush()
    await _refresh_product_aggregate(db, product_id)
    return row, warning
