from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.product import Product
from app.models.sales_channel import SalesChannel


@pytest_asyncio.fixture
async def seed_channel(db_session: AsyncSession) -> SalesChannel:
    ch = SalesChannel(
        name="Etsy",
        platform_fee_pct=Decimal("6.5"),
        fixed_fee=Decimal("0.20"),
    )
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)
    return ch


@pytest_asyncio.fixture
async def seed_product(db_session: AsyncSession, seed_material: Material) -> Product:
    p = Product(
        name="Phone Stand",
        sku="PRD-PLA-0001",
        material_id=seed_material.id,
        unit_price=Decimal("8.99"),
        unit_cost=Decimal("3.50"),
        stock_qty=10,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


def _sale_payload(channel_id=None, product_id=None):
    item = {
        "description": "Phone Stand",
        "quantity": 2,
        "unit_price": 8.99,
        "unit_cost": 3.50,
    }
    if product_id:
        item["product_id"] = str(product_id)
    payload = {
        "date": "2026-03-20",
        "customer_name": "John Doe",
        "status": "paid",
        "items": [item],
    }
    if channel_id:
        payload["channel_id"] = str(channel_id)
    return payload


# ── Sales Channel CRUD ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_channels(client: AsyncClient, seed_channel: SalesChannel):
    resp = await client.get("/api/v1/sales/channels")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(c["name"] == "Etsy" for c in data)


@pytest.mark.asyncio
async def test_create_channel(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/sales/channels",
        headers=auth_headers,
        json={"name": "eBay", "platform_fee_pct": 12.9, "fixed_fee": 0.30},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "eBay"


@pytest.mark.asyncio
async def test_update_channel(client: AsyncClient, auth_headers: dict, seed_channel: SalesChannel):
    resp = await client.put(
        f"/api/v1/sales/channels/{seed_channel.id}",
        headers=auth_headers,
        json={"platform_fee_pct": 7.0},
    )
    assert resp.status_code == 200
    assert float(resp.json()["platform_fee_pct"]) == 7.0


@pytest.mark.asyncio
async def test_delete_channel(client: AsyncClient, auth_headers: dict, seed_channel: SalesChannel):
    resp = await client.delete(f"/api/v1/sales/channels/{seed_channel.id}", headers=auth_headers)
    assert resp.status_code == 204


# ── Sale CRUD ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_sale(client: AsyncClient, auth_headers: dict, seed_channel: SalesChannel):
    payload = _sale_payload(channel_id=seed_channel.id)
    resp = await client.post("/api/v1/sales", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["sale_number"].startswith("S-2026-")
    assert data["customer_name"] == "John Doe"
    assert len(data["items"]) == 1
    assert float(data["subtotal"]) == 17.98
    assert float(data["platform_fees"]) > 0  # Etsy fees applied


@pytest.mark.asyncio
async def test_create_sale_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/sales", json=_sale_payload())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_sales(client: AsyncClient, auth_headers: dict):
    # Create two sales
    for _ in range(2):
        await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    resp = await client.get("/api/v1/sales")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_sales_filter_status(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    resp = await client.get("/api/v1/sales", params={"status": "paid"})
    assert resp.json()["total"] >= 1
    resp2 = await client.get("/api/v1/sales", params={"status": "cancelled"})
    assert resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_sale(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/sales/{sale_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sale_id
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_get_sale_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/sales/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_sale(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/v1/sales/{sale_id}",
        headers=auth_headers,
        json={"customer_name": "Jane Doe", "status": "shipped"},
    )
    assert resp.status_code == 200
    assert resp.json()["customer_name"] == "Jane Doe"
    assert resp.json()["status"] == "shipped"


@pytest.mark.asyncio
async def test_delete_sale(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/sales/{sale_id}", headers=auth_headers)
    assert resp.status_code == 204
    # Verify soft-deleted
    get_resp = await client.get(f"/api/v1/sales/{sale_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_refund_sale(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/sales/{sale_id}/refund", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_refund_already_refunded(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    await client.post(f"/api/v1/sales/{sale_id}/refund", headers=auth_headers)
    resp = await client.post(f"/api/v1/sales/{sale_id}/refund", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sale_inventory_deduction(
    client: AsyncClient, auth_headers: dict, seed_product: Product
):
    payload = _sale_payload(product_id=seed_product.id)
    await client.post("/api/v1/sales", headers=auth_headers, json=payload)
    # Check product stock decreased
    resp = await client.get(f"/api/v1/products/{seed_product.id}")
    assert resp.json()["stock_qty"] == 8  # 10 - 2


@pytest.mark.asyncio
async def test_sale_metrics(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    resp = await client.get("/api/v1/sales/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sales"] >= 1
    assert data["total_revenue"] > 0
