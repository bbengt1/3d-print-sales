"""#262 P2: find-and-merge materials/products."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product


async def _two_materials(db_session):
    a = Material(
        name="PLA Black", brand="A", spool_weight_g=1000, spool_price=Decimal("20"),
        net_usable_g=950, cost_per_g=Decimal("0.02"),
    )
    b = Material(
        name="PLA Blk Dup", brand="B", spool_weight_g=1000, spool_price=Decimal("21"),
        net_usable_g=950, cost_per_g=Decimal("0.022"),
    )
    db_session.add_all([a, b])
    await db_session.flush()
    return a, b


@pytest.mark.asyncio
async def test_merge_materials_rewrites_fk_and_deactivates(client: AsyncClient, auth_headers, db_session):
    survivor, dup = await _two_materials(db_session)
    survivor_id = survivor.id
    dup_id = dup.id
    # Add a receipt on the dup
    db_session.add(
        MaterialReceipt(
            material_id=dup_id, vendor_name="X", purchase_date=datetime.date(2026, 1, 1),
            quantity_purchased_g=Decimal("100"), quantity_remaining_g=Decimal("100"),
            unit_cost_per_g=Decimal("0.05"), total_cost=Decimal("5"),
        )
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/merge/material",
        json={"survivor_id": str(survivor_id), "duplicate_ids": [str(dup_id)]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["survivor_id"] == str(survivor_id)
    assert len(body["merged"]) == 1

    db_session.expire_all()
    # Receipt now points at survivor
    rec = (await db_session.execute(select(MaterialReceipt))).scalar_one()
    assert rec.material_id == survivor_id
    # Dup deactivated, survivor still active
    survivor_row = (await db_session.execute(select(Material).where(Material.id == survivor_id))).scalar_one()
    dup_row = (await db_session.execute(select(Material).where(Material.id == dup_id))).scalar_one()
    assert survivor_row.active is True
    assert dup_row.active is False
    # Audit-log row written
    log = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "merge_duplicate", AuditLog.entity_id == str(dup_id))
        )
    ).scalar_one()
    assert "rewrites" in log.after_snapshot


@pytest.mark.asyncio
async def test_merge_rejects_survivor_in_duplicates(client: AsyncClient, auth_headers, db_session):
    a, _ = await _two_materials(db_session)
    await db_session.commit()
    r = await client.post(
        "/api/v1/merge/material",
        json={"survivor_id": str(a.id), "duplicate_ids": [str(a.id)]},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_merge_rejects_unknown_duplicate(client: AsyncClient, auth_headers, db_session):
    import uuid

    a, _ = await _two_materials(db_session)
    await db_session.commit()
    r = await client.post(
        "/api/v1/merge/material",
        json={"survivor_id": str(a.id), "duplicate_ids": [str(uuid.uuid4())]},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_merge_products_rewrites_fk(client: AsyncClient, auth_headers, db_session):
    m = Material(
        name="PLA m", brand="A", spool_weight_g=1000, spool_price=Decimal("20"),
        net_usable_g=950, cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    survivor = Product(sku="P-A", name="Widget", material_id=m.id, unit_cost=Decimal("3"), unit_price=Decimal("10"))
    dup = Product(sku="P-B", name="Widget Dup", material_id=m.id, unit_cost=Decimal("3"), unit_price=Decimal("10"))
    db_session.add_all([survivor, dup])
    await db_session.flush()
    s_id = survivor.id
    d_id = dup.id
    await db_session.commit()
    r = await client.post(
        "/api/v1/merge/product",
        json={"survivor_id": str(s_id), "duplicate_ids": [str(d_id)]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    db_session.expire_all()
    dup_row = (await db_session.execute(select(Product).where(Product.id == d_id))).scalar_one()
    assert dup_row.is_active is False
