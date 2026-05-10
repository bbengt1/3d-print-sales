"""#317: sales-side COGS FIFO consumption."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.material import Material
from app.models.product import Product
from app.models.production_order import FinishedGoodsLayer
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel
from app.models.setting import Setting
from app.services.cogs_fifo_service import (
    FEATURE_FLAG_KEY,
    compute_sale_cogs,
    consume_finished_goods_layers,
    is_fifo_enabled,
)
from app.services.inventory_accounting_service import post_cogs_for_sale


async def _seed_coa(db_session):
    rows = [
        ("1400", "Finished Goods Inventory", "asset", "debit"),
        ("5000", "Cost of Goods Sold", "cogs", "debit"),
    ]
    for code, name, kind, side in rows:
        existing = (await db_session.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
        if existing is None:
            db_session.add(Account(code=code, name=name, account_type=kind, normal_balance=side))
    await db_session.flush()


async def _product(db_session, sku="P-1") -> Product:
    m = Material(
        name=f"Mat-{sku}", brand="A",
        spool_weight_g=Decimal("1000"), spool_price=Decimal("20"),
        net_usable_g=Decimal("950"), cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    p = Product(sku=sku, name=f"Widget-{sku}", material_id=m.id, unit_cost=Decimal("3"), unit_price=Decimal("10"))
    db_session.add(p)
    await db_session.flush()
    return p


async def _layer(db_session, p, qty: Decimal, unit_cost: Decimal, created_at: datetime.datetime | None = None):
    layer = FinishedGoodsLayer(
        product_id=p.id, qty_total=qty, qty_remaining=qty, unit_cost=unit_cost,
    )
    if created_at is not None:
        layer.created_at = created_at
    db_session.add(layer)
    await db_session.flush()
    return layer


async def _sale_with_item(db_session, p, qty: int = 1, snapshot_unit_cost: Decimal = Decimal("3")) -> tuple[Sale, SaleItem]:
    c = Customer(name="C", email="c@x.x")
    ch = SalesChannel(name=f"ch-{uuid.uuid4().hex[:6]}")
    db_session.add_all([c, ch])
    await db_session.flush()
    sale = Sale(
        sale_number=f"SAL-{uuid.uuid4().hex[:6]}",
        date=datetime.date(2026, 5, 1),
        customer_id=c.id, channel_id=ch.id,
        subtotal=Decimal("10") * qty,
        tax_collected=Decimal("0"),
        shipping_cost=Decimal("0"), platform_fees=Decimal("0"),
        total=Decimal("10") * qty, net_revenue=Decimal("10") * qty,
        status="completed",
    )
    db_session.add(sale)
    await db_session.flush()
    item = SaleItem(
        sale_id=sale.id, product_id=p.id, quantity=qty,
        unit_cost=snapshot_unit_cost, unit_price=Decimal("10"),
        line_total=Decimal("10") * qty,
        description=p.name,
    )
    db_session.add(item)
    await db_session.flush()
    return sale, item


@pytest.mark.asyncio
async def test_flag_default_off(db_session):
    assert (await is_fifo_enabled(db_session)) is False


@pytest.mark.asyncio
async def test_flag_set_via_setting(db_session):
    db_session.add(Setting(key=FEATURE_FLAG_KEY, value="true", notes=""))
    await db_session.commit()
    assert (await is_fifo_enabled(db_session)) is True


@pytest.mark.asyncio
async def test_consume_drains_oldest_first(db_session):
    p = await _product(db_session)
    older = await _layer(
        db_session, p, qty=Decimal("3"), unit_cost=Decimal("2.00"),
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )
    newer = await _layer(
        db_session, p, qty=Decimal("5"), unit_cost=Decimal("4.00"),
        created_at=datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc),
    )
    older_id = older.id
    newer_id = newer.id
    res = await consume_finished_goods_layers(db_session, product_id=p.id, quantity=Decimal("4"))
    assert res.fully_covered
    # 3 from older + 1 from newer = 3*2 + 1*4 = 10
    assert res.layer_cost_total == Decimal("10.0000")
    assert len(res.layer_draws) == 2
    db_session.expire_all()
    older_after = (await db_session.execute(select(FinishedGoodsLayer).where(FinishedGoodsLayer.id == older_id))).scalar_one()
    newer_after = (await db_session.execute(select(FinishedGoodsLayer).where(FinishedGoodsLayer.id == newer_id))).scalar_one()
    assert Decimal(older_after.qty_remaining) == Decimal("0")
    assert Decimal(newer_after.qty_remaining) == Decimal("4")


@pytest.mark.asyncio
async def test_consume_dry_run_does_not_mutate(db_session):
    p = await _product(db_session)
    layer = await _layer(db_session, p, qty=Decimal("5"), unit_cost=Decimal("2.00"))
    layer_id = layer.id
    res = await consume_finished_goods_layers(
        db_session, product_id=p.id, quantity=Decimal("3"), apply=False,
    )
    assert res.layer_cost_total == Decimal("6.0000")
    db_session.expire_all()
    refreshed = (await db_session.execute(select(FinishedGoodsLayer).where(FinishedGoodsLayer.id == layer_id))).scalar_one()
    assert Decimal(refreshed.qty_remaining) == Decimal("5")


@pytest.mark.asyncio
async def test_consume_uncovered_when_layers_short(db_session):
    p = await _product(db_session)
    await _layer(db_session, p, qty=Decimal("2"), unit_cost=Decimal("2.00"))
    res = await consume_finished_goods_layers(db_session, product_id=p.id, quantity=Decimal("5"))
    assert res.quantity_drawn_from_layers == Decimal("2")
    assert res.quantity_uncovered == Decimal("3")
    assert res.fully_covered is False


@pytest.mark.asyncio
async def test_post_cogs_with_flag_off_uses_snapshot(db_session):
    await _seed_coa(db_session)
    p = await _product(db_session)
    await _layer(db_session, p, qty=Decimal("10"), unit_cost=Decimal("4.00"))
    sale, item = await _sale_with_item(db_session, p, qty=2, snapshot_unit_cost=Decimal("3"))
    await db_session.flush()
    await post_cogs_for_sale(db_session, sale, [item])
    cogs_account = (await db_session.execute(select(Account).where(Account.code == "5000"))).scalar_one()
    je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "sale_cogs", JournalEntry.source_id == str(sale.id))
        )
    ).scalar_one()
    cogs_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == je.id, JournalLine.account_id == cogs_account.id)
        )
    ).scalar_one()
    # snapshot cost: 2 * 3 = 6
    assert Decimal(cogs_line.amount) == Decimal("6")
    # Flag is off, so layer should not have been touched
    db_session.expire_all()
    layers = (await db_session.execute(select(FinishedGoodsLayer))).scalars().all()
    assert Decimal(layers[0].qty_remaining) == Decimal("10")


@pytest.mark.asyncio
async def test_post_cogs_with_flag_on_uses_fifo_cost(db_session):
    await _seed_coa(db_session)
    db_session.add(Setting(key=FEATURE_FLAG_KEY, value="true", notes=""))
    p = await _product(db_session)
    # Two layers at different costs; FIFO should pick the older.
    await _layer(
        db_session, p, qty=Decimal("3"), unit_cost=Decimal("2.50"),
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )
    await _layer(
        db_session, p, qty=Decimal("5"), unit_cost=Decimal("5.00"),
        created_at=datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc),
    )
    sale, item = await _sale_with_item(db_session, p, qty=4, snapshot_unit_cost=Decimal("3"))
    await db_session.flush()
    await post_cogs_for_sale(db_session, sale, [item])
    cogs_account = (await db_session.execute(select(Account).where(Account.code == "5000"))).scalar_one()
    je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "sale_cogs", JournalEntry.source_id == str(sale.id))
        )
    ).scalar_one()
    cogs_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == je.id, JournalLine.account_id == cogs_account.id)
        )
    ).scalar_one()
    # FIFO: 3 @ 2.50 + 1 @ 5.00 = 7.50 + 5.00 = 12.50
    assert Decimal(cogs_line.amount) == Decimal("12.5")


@pytest.mark.asyncio
async def test_post_cogs_with_flag_on_falls_back_when_no_layers(db_session):
    await _seed_coa(db_session)
    db_session.add(Setting(key=FEATURE_FLAG_KEY, value="true", notes=""))
    p = await _product(db_session)
    sale, item = await _sale_with_item(db_session, p, qty=2, snapshot_unit_cost=Decimal("3"))
    await db_session.flush()
    await post_cogs_for_sale(db_session, sale, [item])
    cogs_account = (await db_session.execute(select(Account).where(Account.code == "5000"))).scalar_one()
    je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "sale_cogs", JournalEntry.source_id == str(sale.id))
        )
    ).scalar_one()
    cogs_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == je.id, JournalLine.account_id == cogs_account.id)
        )
    ).scalar_one()
    # No layers → snapshot cost = 2 * 3 = 6
    assert Decimal(cogs_line.amount) == Decimal("6")


@pytest.mark.asyncio
async def test_compute_sale_cogs_dry_run(db_session):
    p = await _product(db_session)
    await _layer(db_session, p, qty=Decimal("5"), unit_cost=Decimal("4.00"))
    sale, item = await _sale_with_item(db_session, p, qty=3, snapshot_unit_cost=Decimal("3"))
    await db_session.flush()
    breakdown = await compute_sale_cogs(db_session, [item], apply=False)
    assert breakdown["from_layers"] == Decimal("12.0000")  # 3 * 4
    assert breakdown["from_snapshot"] == Decimal("0")
    db_session.expire_all()
    layers = (await db_session.execute(select(FinishedGoodsLayer))).scalars().all()
    assert Decimal(layers[0].qty_remaining) == Decimal("5")  # untouched
