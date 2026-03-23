from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.product import Product
from app.models.user import User


@pytest.mark.asyncio
async def test_non_admin_inventory_adjustment_creates_pending_approval(client, user_headers, db_session: AsyncSession, seed_material: Material):
    product = Product(sku="APR-001", name="Approval Widget", material_id=seed_material.id, stock_qty=10, reorder_point=2)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    resp = await client.post(
        "/api/v1/inventory/transactions",
        headers=user_headers,
        json={"product_id": str(product.id), "type": "adjustment", "quantity": 2, "unit_cost": 1.0, "notes": "Need count correction"},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_inventory_adjustment_requires_reason(client, auth_headers, db_session: AsyncSession, seed_material: Material):
    product = Product(sku="APR-002", name="Reason Widget", material_id=seed_material.id, stock_qty=10, reorder_point=2)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    resp = await client.post(
        "/api/v1/inventory/transactions",
        headers=auth_headers,
        json={"product_id": str(product.id), "type": "adjustment", "quantity": 2, "unit_cost": 1.0},
    )
    assert resp.status_code == 400
    assert "documented reason" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_admin_refund_creates_pending_request_and_admin_can_approve(client, auth_headers, user_headers, db_session: AsyncSession, seed_material: Material):
    product = Product(sku="APR-003", name="Refund Widget", material_id=seed_material.id, stock_qty=10, reorder_point=2)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    sale_resp = await client.post(
        "/api/v1/sales",
        headers=auth_headers,
        json={
            "date": "2026-03-23",
            "customer_name": "Approval Customer",
            "status": "paid",
            "items": [{"product_id": str(product.id), "description": "Refund Widget", "quantity": 1, "unit_price": 20.0, "unit_cost": 8.0}],
        },
    )
    sale = sale_resp.json()

    refund_resp = await client.post(
        f"/api/v1/sales/{sale['id']}/refund",
        headers=user_headers,
        json={"reason": "Customer return"},
    )
    assert refund_resp.status_code == 202

    approvals = await client.get("/api/v1/approvals", headers=auth_headers, params={"status_filter": "pending"})
    assert approvals.status_code == 200
    pending = next(a for a in approvals.json() if a["action_type"] == "sale_refund")

    approve_resp = await client.post(f"/api/v1/approvals/{pending['id']}/approve", headers=auth_headers, json={"decision_notes": "Approved"})
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    sale_get = await client.get(f"/api/v1/sales/{sale['id']}", headers=auth_headers)
    assert sale_get.status_code == 200
    assert sale_get.json()["status"] == "refunded"
