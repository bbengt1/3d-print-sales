"""#262 P2: inventory starting-balances CSV import."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.inventory_transaction import InventoryTransaction
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product
from app.models.supply import Supply


async def _seed(db_session):
    m = Material(
        name="PLA Black", brand="Generic", spool_weight_g=1000, spool_price=Decimal("20"),
        net_usable_g=950, cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    p = Product(sku="WIDGET-1", name="Widget", material_id=m.id, unit_cost=Decimal("3"), unit_price=Decimal("10"))
    db_session.add(p)
    s = Supply(name="Resin Cleaner", unit="L", unit_cost=Decimal("5"), quantity_on_hand=Decimal("0"))
    db_session.add(s)
    await db_session.flush()
    return m, p, s


@pytest.mark.asyncio
async def test_csv_imports_material_receipt(client: AsyncClient, auth_headers, db_session):
    m, _, _ = await _seed(db_session)
    await db_session.commit()
    csv = (
        "item_kind,item_identifier,quantity,unit_cost,notes\n"
        "material,PLA Black,950,0.02,Opening lot\n"
    ).encode()
    r = await client.post(
        "/api/v1/inventory/starting-balances/inventory.csv?as_of=2026-01-01",
        files={"file": ("inv.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 1
    rec = (await db_session.execute(select(MaterialReceipt).where(MaterialReceipt.material_id == m.id))).scalar_one()
    assert rec.vendor_name == "Opening Balance"
    assert Decimal(rec.quantity_remaining_g) == Decimal("950")


@pytest.mark.asyncio
async def test_csv_imports_product_and_supply(client: AsyncClient, auth_headers, db_session):
    _, p, s = await _seed(db_session)
    p_id = p.id
    s_id = s.id
    await db_session.commit()
    csv = (
        "item_kind,item_identifier,quantity,unit_cost\n"
        "product,WIDGET-1,12,3.50\n"
        "supply,Resin Cleaner,4,5.00\n"
    ).encode()
    r = await client.post(
        "/api/v1/inventory/starting-balances/inventory.csv",
        files={"file": ("i.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["imported"] == 2
    db_session.expire_all()
    refreshed_p = (await db_session.execute(select(Product).where(Product.id == p_id))).scalar_one()
    assert refreshed_p.stock_qty == 12
    refreshed_s = (await db_session.execute(select(Supply).where(Supply.id == s_id))).scalar_one()
    assert Decimal(refreshed_s.quantity_on_hand) == Decimal("4")
    txs = (await db_session.execute(select(InventoryTransaction).where(InventoryTransaction.product_id == p_id))).scalars().all()
    assert len(txs) == 1
    assert txs[0].type == "adjustment"


@pytest.mark.asyncio
async def test_activity_guard_blocks_without_force(client: AsyncClient, auth_headers, db_session):
    m, _, _ = await _seed(db_session)
    # Pre-existing receipt should trip the guard
    db_session.add(
        MaterialReceipt(
            material_id=m.id, vendor_name="Real Vendor",
            purchase_date=datetime.date(2026, 1, 1),
            quantity_purchased_g=Decimal("100"),
            quantity_remaining_g=Decimal("100"),
            unit_cost_per_g=Decimal("0.05"),
            total_cost=Decimal("5"),
        )
    )
    await db_session.commit()
    csv = "item_kind,item_identifier,quantity,unit_cost\nmaterial,PLA Black,500,0.02\n".encode()
    r = await client.post(
        "/api/v1/inventory/starting-balances/inventory.csv",
        files={"file": ("i.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    body = r.json()
    assert body["imported"] == 0
    assert "prior activity" in body["rows"][0]["error"]
    # With force=true succeeds
    r2 = await client.post(
        "/api/v1/inventory/starting-balances/inventory.csv?force=true",
        files={"file": ("i.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    assert r2.json()["imported"] == 1


@pytest.mark.asyncio
async def test_unknown_item_returns_per_row_error(client: AsyncClient, auth_headers, db_session):
    csv = "item_kind,item_identifier,quantity,unit_cost\nmaterial,Nonexistent,10,1\n".encode()
    r = await client.post(
        "/api/v1/inventory/starting-balances/inventory.csv",
        files={"file": ("i.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 0
    assert "not found" in body["rows"][0]["error"]


@pytest.mark.asyncio
async def test_missing_columns_400(client: AsyncClient, auth_headers):
    csv = "foo,bar\nx,y\n".encode()
    r = await client.post(
        "/api/v1/inventory/starting-balances/inventory.csv",
        files={"file": ("i.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 400
