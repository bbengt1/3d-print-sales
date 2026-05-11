"""#318 P2: ProductLocationStock SoT + per-location decrement + soft-warn + in-transit."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.inventory_location import InventoryLocation
from app.models.material import Material
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.setting import Setting
from app.services import product_location_stock_service as pls
from app.services.inventory_transfer_service import (
    cancel_transfer,
    create_transfer,
    receive_transfer,
    ship_transfer,
)
from app.services.sales_service import (
    create_sale_with_items,
    deduct_inventory_for_sale,
    restore_inventory_for_refund,
)


async def _two_locs(db):
    a = InventoryLocation(name="Workshop")
    b = InventoryLocation(name="Showroom")
    db.add_all([a, b])
    await db.flush()
    return a, b


async def _product(db, stock=10) -> Product:
    m = Material(
        name="PLA",
        brand="Generic",
        spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"),
        net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.02"),
    )
    db.add(m)
    await db.flush()
    p = Product(
        sku="PROD-1",
        name="Widget",
        material_id=m.id,
        unit_cost=Decimal("3"),
        unit_price=Decimal("10"),
        stock_qty=stock,
    )
    db.add(p)
    await db.flush()
    return p


class _Item:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self):
        return dict(self.__dict__)


@pytest.mark.asyncio
async def test_adjust_creates_and_updates_row_and_aggregate(db_session):
    a, _ = await _two_locs(db_session)
    p = await _product(db_session, stock=0)

    row, warn = await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(5))
    assert warn is None
    assert row.on_hand_qty == Decimal(5)
    await db_session.refresh(p)
    assert p.stock_qty == 5

    row2, _ = await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(-2))
    assert row2.on_hand_qty == Decimal(3)
    await db_session.refresh(p)
    assert p.stock_qty == 3


@pytest.mark.asyncio
async def test_soft_warn_on_negative(db_session):
    a, _ = await _two_locs(db_session)
    p = await _product(db_session, stock=0)

    _, warn = await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(-3))
    assert warn is not None
    assert warn.projected_on_hand == Decimal(-3)


@pytest.mark.asyncio
async def test_hard_block_when_setting_enabled(db_session):
    a, _ = await _two_locs(db_session)
    p = await _product(db_session, stock=0)
    db_session.add(Setting(key=pls.PREVENT_NEGATIVE_STOCK_KEY, value="true"))
    await db_session.flush()

    with pytest.raises(pls.NegativeStockBlockedError):
        await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(-1))


@pytest.mark.asyncio
async def test_transfer_ship_decrements_source_receive_increments_dest(db_session):
    a, b = await _two_locs(db_session)
    p = await _product(db_session, stock=0)
    # Seed 10 at source.
    await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(10))

    transfer = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "product", "product_id": p.id, "quantity": Decimal(4)}],
    )

    await ship_transfer(db_session, transfer.id)
    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=a.id) == Decimal(6)
    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=b.id) == Decimal(0)
    # In-transit is visible at destination.
    assert await pls.in_transit_to(db_session, product_id=p.id, location_id=b.id) == Decimal(4)

    await receive_transfer(db_session, transfer.id)
    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=b.id) == Decimal(4)
    assert await pls.in_transit_to(db_session, product_id=p.id, location_id=b.id) == Decimal(0)


@pytest.mark.asyncio
async def test_cancel_in_transit_restores_source(db_session):
    a, b = await _two_locs(db_session)
    p = await _product(db_session, stock=0)
    await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(10))

    transfer = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "product", "product_id": p.id, "quantity": Decimal(4)}],
    )
    await ship_transfer(db_session, transfer.id)
    await cancel_transfer(db_session, transfer.id)
    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=a.id) == Decimal(10)


@pytest.mark.asyncio
async def test_sale_decrements_resolved_fulfillment_location(db_session):
    a, b = await _two_locs(db_session)
    p = await _product(db_session, stock=0)
    await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(10))
    await pls.adjust(db_session, product_id=p.id, location_id=b.id, delta=Decimal(10))
    await db_session.commit()

    sale = await create_sale_with_items(
        db_session,
        user_id=None,
        date=dt.date.today(),
        customer_id=None,
        customer_name=None,
        channel_id=None,
        tax_profile_id=None,
        tax_treatment="seller_collected",
        shipping_charged=Decimal(0),
        shipping_cost=Decimal(0),
        tax_collected=Decimal(0),
        payment_method=None,
        tracking_number=None,
        shipping_recipient_name=None,
        shipping_company=None,
        shipping_address_line1=None,
        shipping_address_line2=None,
        shipping_city=None,
        shipping_state=None,
        shipping_postal_code=None,
        shipping_country=None,
        notes=None,
        status="pending",
        items=[_Item(product_id=p.id, job_id=None, description="Widget", quantity=3, unit_price=Decimal("10"), unit_cost=Decimal("3"))],
    )
    sale.fulfillment_location_id = b.id
    await db_session.flush()

    # Hook: the create-with-items path already deducted via the resolver
    # using sale.fulfillment_location_id == None (so default→Default).
    # Re-run via explicit deduct_inventory_for_sale to verify the
    # explicit-location branch.
    items = (await db_session.execute(select(SaleItem).where(SaleItem.sale_id == sale.id))).scalars().all()
    # Manually restore so we can re-test deduct against b.
    for item in items:
        await pls.adjust(db_session, product_id=item.product_id, location_id=a.id, delta=Decimal(item.quantity))
    await deduct_inventory_for_sale(db_session, sale.id, items, user_id=None)

    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=b.id) == Decimal(7)


@pytest.mark.asyncio
async def test_sale_refund_restores_to_fulfillment_location(db_session):
    a, b = await _two_locs(db_session)
    p = await _product(db_session, stock=0)
    await pls.adjust(db_session, product_id=p.id, location_id=b.id, delta=Decimal(10))
    await db_session.flush()

    sale = Sale(
        sale_number="S-1",
        date=dt.date.today(),
        status="pending",
        fulfillment_location_id=b.id,
    )
    db_session.add(sale)
    await db_session.flush()
    item = SaleItem(
        sale_id=sale.id,
        product_id=p.id,
        description="Widget",
        quantity=4,
        unit_price=Decimal("10"),
        line_total=Decimal("40"),
        unit_cost=Decimal("3"),
    )
    db_session.add(item)
    await db_session.flush()

    await deduct_inventory_for_sale(db_session, sale.id, [item])
    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=b.id) == Decimal(6)

    # Reload with items relationship.
    full = (
        await db_session.execute(
            select(Sale).where(Sale.id == sale.id)
        )
    ).scalar_one()
    # SaleItem relationship lazy load is tricky in async; fetch manually.
    full_items = (
        await db_session.execute(
            select(SaleItem).where(SaleItem.sale_id == sale.id)
        )
    ).scalars().all()

    # Restore_inventory uses sale.items; emulate by attaching.
    class _SaleLike:
        def __init__(self, sale, items):
            self.id = sale.id
            self.sale_number = sale.sale_number
            self.fulfillment_location_id = sale.fulfillment_location_id
            self.items = items

    await restore_inventory_for_refund(db_session, _SaleLike(full, full_items))
    assert await pls.get_on_hand(db_session, product_id=p.id, location_id=b.id) == Decimal(10)


@pytest.mark.asyncio
async def test_product_stock_endpoint_reports_in_transit(client: AsyncClient, auth_headers, db_session):
    a, b = await _two_locs(db_session)
    p = await _product(db_session, stock=0)
    await pls.adjust(db_session, product_id=p.id, location_id=a.id, delta=Decimal(10))
    transfer = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "product", "product_id": p.id, "quantity": Decimal(3)}],
    )
    await ship_transfer(db_session, transfer.id)
    await db_session.commit()

    r = await client.get(f"/api/v1/inventory/locations/{b.id}/product-stock", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 0 or all(Decimal(row["on_hand_qty"]) == Decimal(0) for row in body)

    r2 = await client.get(f"/api/v1/inventory/locations/{a.id}/product-stock", headers=auth_headers)
    assert r2.status_code == 200
    row = [row for row in r2.json() if row["product_id"] == str(p.id)][0]
    assert Decimal(row["on_hand_qty"]) == Decimal(7)
    # Source has no in-transit-to itself.
    assert Decimal(row["in_transit_to_qty"]) == Decimal(0)


@pytest.mark.asyncio
async def test_prevent_negative_stock_toggle_round_trip(client: AsyncClient, auth_headers, db_session):
    r0 = await client.get("/api/v1/inventory/prevent-negative-stock", headers=auth_headers)
    assert r0.status_code == 200
    assert r0.json()["enabled"] is False

    r1 = await client.put(
        "/api/v1/inventory/prevent-negative-stock",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["enabled"] is True

    r2 = await client.get("/api/v1/inventory/prevent-negative-stock", headers=auth_headers)
    assert r2.json()["enabled"] is True
