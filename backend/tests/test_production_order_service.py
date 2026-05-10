from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product
from app.models.product_bom_item import ProductBOMItem
from app.models.production_order import (
    FinishedGoodsLayer,
    ProductionOrder,
    ProductionOrderConsumption,
)
from app.services.production_order_service import (
    ProductionOrderError,
    cancel_order,
    close_order,
    create_order,
)


async def _setup(db_session, *, qty_g="1000", cost_per_g="0.10"):
    mat = Material(
        name="PLA Black",
        brand="TestBrand",
        spool_weight_g=Decimal("1000"),
        spool_price=Decimal("100"),
        net_usable_g=Decimal("950"),
        cost_per_g=Decimal(cost_per_g),
    )
    db_session.add(mat)
    await db_session.flush()
    receipt = MaterialReceipt(
        material_id=mat.id,
        vendor_name="Acme",
        purchase_date=datetime.date(2026, 4, 1),
        quantity_purchased_g=Decimal(qty_g),
        quantity_remaining_g=Decimal(qty_g),
        unit_cost_per_g=Decimal(cost_per_g),
        landed_cost_total=Decimal("0"),
        landed_cost_per_g=Decimal("0"),
        total_cost=Decimal(qty_g) * Decimal(cost_per_g),
    )
    db_session.add(receipt)
    product = Product(sku="WIDGET-1", name="Widget", material_id=mat.id)
    db_session.add(product)
    await db_session.flush()
    bom = ProductBOMItem(
        product_id=product.id,
        component_type="material",
        material_id=mat.id,
        quantity=Decimal("50"),  # 50 g per unit
        unit="g",
    )
    db_session.add(bom)
    await db_session.flush()
    return mat, product, receipt


@pytest.mark.asyncio
async def test_create_order_snapshots_bom(db_session):
    _, product, _ = await _setup(db_session)
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("10"))
    assert order.order_number.startswith("PRD-")
    assert order.status == "planned"
    consumptions = (
        await db_session.execute(
            select(ProductionOrderConsumption).where(
                ProductionOrderConsumption.production_order_id == order.id
            )
        )
    ).scalars().all()
    assert len(consumptions) == 1
    assert consumptions[0].planned_qty == Decimal("500.0000")  # 50 g × 10 units


@pytest.mark.asyncio
async def test_create_order_zero_qty_rejected(db_session):
    _, product, _ = await _setup(db_session)
    with pytest.raises(ProductionOrderError):
        await create_order(db_session, product_id=product.id, output_quantity=Decimal("0"))


@pytest.mark.asyncio
async def test_close_order_consumes_fifo_and_posts_je(db_session):
    mat, product, receipt = await _setup(db_session, qty_g="1000", cost_per_g="0.10")
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("10"))
    closed = await close_order(db_session, order.id)
    assert closed.status == "completed"
    # 50 g × 10 units = 500 g consumed; cost = 500 × 0.10 = 50.00
    assert Decimal(closed.total_material_cost).quantize(Decimal("0.01")) == Decimal("50.00")
    assert closed.total_finished_goods_value == closed.total_material_cost
    assert closed.journal_entry_id is not None
    # Receipt drained 500 g
    refreshed = (await db_session.execute(select(MaterialReceipt).where(MaterialReceipt.id == receipt.id))).scalar_one()
    assert refreshed.quantity_remaining_g == Decimal("500")
    # Layer created
    layers = (await db_session.execute(select(FinishedGoodsLayer).where(FinishedGoodsLayer.production_order_id == order.id))).scalars().all()
    assert len(layers) == 1
    assert layers[0].qty_total == Decimal("10")
    assert layers[0].qty_remaining == Decimal("10")
    # Unit cost 50.00 / 10 = 5.00
    assert layers[0].unit_cost == Decimal("5.000000")


@pytest.mark.asyncio
async def test_close_order_uses_landed_cost_when_set(db_session):
    mat, product, receipt = await _setup(db_session, qty_g="1000", cost_per_g="0.10")
    receipt.landed_cost_per_g = Decimal("0.15")  # operator added freight-in
    await db_session.flush()
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("10"))
    closed = await close_order(db_session, order.id)
    # 500 g × 0.15 = 75.00
    assert Decimal(closed.total_material_cost).quantize(Decimal("0.01")) == Decimal("75.00")


@pytest.mark.asyncio
async def test_close_order_walks_multiple_receipts_in_order(db_session):
    mat, product, receipt = await _setup(db_session, qty_g="100", cost_per_g="0.10")
    # Add a second receipt purchased later, more expensive
    later_receipt = MaterialReceipt(
        material_id=mat.id,
        vendor_name="Acme",
        purchase_date=datetime.date(2026, 5, 1),
        quantity_purchased_g=Decimal("1000"),
        quantity_remaining_g=Decimal("1000"),
        unit_cost_per_g=Decimal("0.20"),
        landed_cost_total=Decimal("0"),
        landed_cost_per_g=Decimal("0"),
        total_cost=Decimal("200"),
    )
    db_session.add(later_receipt)
    await db_session.flush()

    # Need 500g; first receipt has 100g at 0.10, then second supplies 400g at 0.20
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("10"))
    closed = await close_order(db_session, order.id)
    # cost = 100 × 0.10 + 400 × 0.20 = 10 + 80 = 90.00
    assert Decimal(closed.total_material_cost).quantize(Decimal("0.01")) == Decimal("90.00")
    earlier = (await db_session.execute(select(MaterialReceipt).where(MaterialReceipt.id == receipt.id))).scalar_one()
    assert earlier.quantity_remaining_g == Decimal("0")
    later = (await db_session.execute(select(MaterialReceipt).where(MaterialReceipt.id == later_receipt.id))).scalar_one()
    assert later.quantity_remaining_g == Decimal("600")  # 1000 - 400


@pytest.mark.asyncio
async def test_cannot_close_already_closed(db_session):
    _, product, _ = await _setup(db_session)
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("5"))
    await close_order(db_session, order.id)
    with pytest.raises(ProductionOrderError):
        await close_order(db_session, order.id)


@pytest.mark.asyncio
async def test_cancel_planned_order(db_session):
    _, product, _ = await _setup(db_session)
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("5"))
    cancelled = await cancel_order(db_session, order.id)
    assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_cannot_cancel_completed_order(db_session):
    _, product, _ = await _setup(db_session)
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("5"))
    await close_order(db_session, order.id)
    with pytest.raises(ProductionOrderError):
        await cancel_order(db_session, order.id)


@pytest.mark.asyncio
async def test_close_order_with_no_bom_creates_zero_value_layer(db_session):
    """A product without a BOM produces a zero-cost layer — useful as a
    starting-balance shortcut. Doesn't post a JE since total_value == 0."""
    mat = Material(
        name="x", brand="x",
        spool_weight_g=Decimal("1000"), spool_price=Decimal("10"),
        net_usable_g=Decimal("950"), cost_per_g=Decimal("0.01"),
    )
    db_session.add(mat)
    await db_session.flush()
    product = Product(sku="NO-BOM", name="No BOM", material_id=mat.id)
    db_session.add(product)
    await db_session.flush()
    order = await create_order(db_session, product_id=product.id, output_quantity=Decimal("5"))
    closed = await close_order(db_session, order.id)
    assert closed.status == "completed"
    assert closed.total_material_cost == Decimal("0")
    assert closed.journal_entry_id is None  # no JE when value is 0
    layers = (await db_session.execute(select(FinishedGoodsLayer).where(FinishedGoodsLayer.production_order_id == order.id))).scalars().all()
    assert len(layers) == 1
    assert layers[0].unit_cost == Decimal("0")
