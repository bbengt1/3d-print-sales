from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


@pytest.mark.asyncio
async def test_inventory_adjustment_writes_audit_log(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_material):
    product = Product(
        sku="PRD-AUD-0001",
        name="Audit Widget",
        material_id=seed_material.id,
        stock_qty=10,
        reorder_point=5,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    resp = await client.post(
        "/api/v1/inventory/transactions",
        headers=auth_headers,
        json={
            "product_id": str(product.id),
            "type": "adjustment",
            "quantity": 3,
            "unit_cost": 1.25,
            "notes": "Cycle count correction",
        },
    )
    assert resp.status_code == 201

    logs = await client.get("/api/v1/audit/logs", headers=auth_headers, params={"entity_type": "inventory_transaction"})
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) >= 1
    assert data[0]["action"] == "create"
    assert data[0]["reason"] == "Cycle count correction"
    assert data[0]["before_snapshot"]["stock_qty"] == 10
    assert data[0]["after_snapshot"]["stock_qty"] == 13


@pytest.mark.asyncio
async def test_setting_update_writes_audit_log(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    from app.models.setting import Setting

    db_session.add(Setting(key="platform_fee_pct", value="9.5", notes="Platform fee"))
    await db_session.commit()

    resp = await client.put(
        "/api/v1/settings/platform_fee_pct",
        headers=auth_headers,
        json={"value": "11.0"},
    )
    assert resp.status_code == 200

    logs = await client.get("/api/v1/audit/logs", headers=auth_headers, params={"entity_type": "setting", "entity_id": "platform_fee_pct"})
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) >= 1
    assert data[0]["action"] == "update"
    assert data[0]["before_snapshot"]["value"] == "9.5"
    assert data[0]["after_snapshot"]["value"] == "11.0"


@pytest.mark.asyncio
async def test_non_admin_cannot_read_audit_logs(client: AsyncClient, user_headers: dict):
    resp = await client.get("/api/v1/audit/logs", headers=user_headers)
    assert resp.status_code == 403
