"""Regression for Codex P1 review on PR #293.

`production_order_service.close_order` previously called
`create_journal_entry` (which commits internally) BEFORE setting the order
to `completed` and BEFORE inserting the finished-goods layer. If any later
step raised, the JE — and the receipt FIFO draws — were already durable
while the order remained `planned`, leaving inventory and accounting
mutated without a corresponding closed order.

The fix passes `commit=False` to `create_journal_entry` so the JE write,
the status/completed_at update, and the finished-goods layer insert all
share the surrounding transaction. A failure after the JE write must roll
back every effect of the close attempt.

This test forces a layer-insert failure AFTER the JE row has been added
(via monkeypatching `FinishedGoodsLayer.__init__` to raise) and asserts:

  - close_order raises
  - no JournalEntry was persisted for the production order
  - the production order's status is still 'planned'
  - the order has no journal_entry_id pointer
  - no FinishedGoodsLayer was persisted for the order
  - no MaterialReceipt FIFO draw persisted (quantity_remaining_g restored)
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.journal_entry import JournalEntry
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product
from app.models.product_bom_item import ProductBOMItem
from app.models.production_order import (
    FinishedGoodsLayer,
    ProductionOrder,
)
from app.services import production_order_service
from app.services.production_order_service import close_order, create_order


async def _seed(db_session):
    mat = Material(
        name="PLA Atomic",
        brand="TestBrand",
        spool_weight_g=Decimal("1000"),
        spool_price=Decimal("100"),
        net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.10"),
    )
    db_session.add(mat)
    await db_session.flush()
    receipt = MaterialReceipt(
        material_id=mat.id,
        vendor_name="Acme",
        purchase_date=datetime.date(2026, 4, 1),
        quantity_purchased_g=Decimal("1000"),
        quantity_remaining_g=Decimal("1000"),
        unit_cost_per_g=Decimal("0.10"),
        landed_cost_total=Decimal("0"),
        landed_cost_per_g=Decimal("0"),
        total_cost=Decimal("100"),
    )
    db_session.add(receipt)
    product = Product(sku="WIDGET-ATOMIC", name="Widget", material_id=mat.id)
    db_session.add(product)
    await db_session.flush()
    bom = ProductBOMItem(
        product_id=product.id,
        component_type="material",
        material_id=mat.id,
        quantity=Decimal("50"),
        unit="g",
    )
    db_session.add(bom)
    await db_session.flush()
    # Commit seed so an outer rollback inside close_order would not erase
    # the test's own setup. The behaviour under test is whether close_order's
    # own work is rolled back as a unit when a later step raises.
    await db_session.commit()
    return mat, product, receipt


@pytest.mark.asyncio
async def test_close_order_rolls_back_je_when_layer_insert_fails(
    db_session, monkeypatch
):
    mat, product, receipt = await _seed(db_session)
    receipt_id = receipt.id
    order = await create_order(
        db_session, product_id=product.id, output_quantity=Decimal("10")
    )
    await db_session.commit()
    order_id = order.id

    boom = RuntimeError("simulated finished-goods layer insertion failure")

    real_init = FinishedGoodsLayer.__init__

    def exploding_init(self, *args, **kwargs):  # noqa: ANN001 - test stub
        # Detonate only when close_order tries to materialise the new
        # layer; this runs AFTER `create_journal_entry` has already added
        # the JE row to the session.
        raise boom

    monkeypatch.setattr(FinishedGoodsLayer, "__init__", exploding_init)

    with pytest.raises(RuntimeError, match="simulated finished-goods layer"):
        await close_order(db_session, order_id)

    # Restore so post-failure assertions can construct ORM objects normally
    # (and so the rollback below isn't poisoned by the patch).
    monkeypatch.setattr(FinishedGoodsLayer, "__init__", real_init)

    # The session is in a failed state; roll it back so we can read.
    await db_session.rollback()

    # No journal entry persisted for this order.
    persisted_entries = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.source_type == "production_order",
                JournalEntry.source_id == str(order_id),
            )
        )
    ).scalars().all()
    assert persisted_entries == [], (
        "JE was persisted despite a later step failing — close_order is "
        "not atomic across journal posting and layer creation."
    )

    # Order is still 'planned' and has no JE pointer.
    refreshed = (
        await db_session.execute(
            select(ProductionOrder).where(ProductionOrder.id == order_id)
        )
    ).scalar_one()
    assert refreshed.status == "planned", (
        f"Order status leaked to {refreshed.status!r} after a failed close"
    )
    assert refreshed.completed_at is None
    assert refreshed.journal_entry_id is None

    # No finished-goods layer for this order.
    layers = (
        await db_session.execute(
            select(FinishedGoodsLayer).where(
                FinishedGoodsLayer.production_order_id == order_id
            )
        )
    ).scalars().all()
    assert layers == []

    # FIFO draw rolled back: receipt is back at its full balance.
    refreshed_receipt = (
        await db_session.execute(
            select(MaterialReceipt).where(MaterialReceipt.id == receipt_id)
        )
    ).scalar_one()
    assert refreshed_receipt.quantity_remaining_g == Decimal("1000"), (
        "Material receipt FIFO draw persisted despite the close failing — "
        "the JE/layer/consumption writes must share one transaction."
    )


@pytest.mark.asyncio
async def test_close_order_uses_row_lock(db_session):
    """Smoke test that the SELECT for the production order is emitted with
    `FOR UPDATE` semantics on dialects that support it. SQLite (test DB)
    silently ignores the clause, so we just exercise the path to make sure
    the lock hint does not break the close on the supported test backend.
    """
    mat, product, _ = await _seed(db_session)
    order = await create_order(
        db_session, product_id=product.id, output_quantity=Decimal("10")
    )
    await db_session.commit()
    closed = await close_order(db_session, order.id)
    assert closed.status == "completed"
    # And `with_for_update()` is still wired on the read — guard against
    # someone removing it inadvertently.
    import inspect

    src = inspect.getsource(production_order_service.close_order)
    assert "with_for_update" in src, (
        "close_order must use with_for_update() to serialize concurrent "
        "/close requests against the same production order."
    )
