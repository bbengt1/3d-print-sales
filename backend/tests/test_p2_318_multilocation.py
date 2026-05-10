"""#318 P2: per-location stock snapshot + default fulfillment location."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.inventory_location import (
    InventoryLocation,
    InventoryTransfer,
    InventoryTransferLine,
)
from app.models.material import Material
from app.models.product import Product
from app.models.setting import Setting


async def _two_locations(db_session):
    a = InventoryLocation(name="Workshop")
    b = InventoryLocation(name="Showroom")
    db_session.add_all([a, b])
    await db_session.flush()
    return a, b


async def _product(db_session):
    m = Material(name="PLA", brand="Generic", spool_weight_g=1000, spool_price=Decimal("20"), net_usable_g=950, cost_per_g=Decimal("0.02"))
    db_session.add(m)
    await db_session.flush()
    p = Product(sku="PROD-1", name="Widget", material_id=m.id, unit_cost=Decimal("3"), unit_price=Decimal("10"))
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_stock_snapshot_reflects_completed_transfers(client: AsyncClient, auth_headers, db_session):
    a, b = await _two_locations(db_session)
    p = await _product(db_session)
    transfer = InventoryTransfer(
        transfer_number="T-1",
        from_location_id=a.id,
        to_location_id=b.id,
        status="completed",
    )
    db_session.add(transfer)
    await db_session.flush()
    db_session.add(InventoryTransferLine(transfer_id=transfer.id, kind="product", product_id=p.id, quantity=Decimal("4")))
    await db_session.commit()

    r = await client.get(f"/api/v1/inventory/locations/{b.id}/stock-snapshot", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    products = {row["product_id"]: Decimal(row["qty"]) for row in body["products"]}
    assert products[str(p.id)] == Decimal("4")

    r2 = await client.get(f"/api/v1/inventory/locations/{a.id}/stock-snapshot", headers=auth_headers)
    products_a = {row["product_id"]: Decimal(row["qty"]) for row in r2.json()["products"]}
    assert products_a[str(p.id)] == Decimal("-4")


@pytest.mark.asyncio
async def test_default_fulfillment_location_set_get(client: AsyncClient, auth_headers, db_session):
    a, _ = await _two_locations(db_session)
    await db_session.commit()
    g0 = await client.get("/api/v1/inventory/default-fulfillment-location", headers=auth_headers)
    assert g0.status_code == 200
    assert g0.json()["location_id"] is None

    s = await client.put(
        "/api/v1/inventory/default-fulfillment-location",
        json={"location_id": str(a.id)},
        headers=auth_headers,
    )
    assert s.status_code == 200
    assert s.json()["location_id"] == str(a.id)

    g1 = await client.get("/api/v1/inventory/default-fulfillment-location", headers=auth_headers)
    assert g1.json()["location_id"] == str(a.id)

    # Clearing
    s2 = await client.put(
        "/api/v1/inventory/default-fulfillment-location",
        json={"location_id": None},
        headers=auth_headers,
    )
    assert s2.json()["location_id"] is None


@pytest.mark.asyncio
async def test_default_fulfillment_location_unknown_404(client: AsyncClient, auth_headers, db_session):
    import uuid
    bogus = str(uuid.uuid4())
    r = await client.put(
        "/api/v1/inventory/default-fulfillment-location",
        json={"location_id": bogus},
        headers=auth_headers,
    )
    assert r.status_code == 404
