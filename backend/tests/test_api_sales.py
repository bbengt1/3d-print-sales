from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
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


def _sale_payload(channel_id=None, product_id=None, shipping_cost=0, shipping_charged=0):
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
        "shipping_cost": shipping_cost,
        "shipping_charged": shipping_charged,
        "shipping_recipient_name": "John Doe",
        "shipping_address_line1": "123 Maker Lane",
        "shipping_city": "Austin",
        "shipping_state": "TX",
        "shipping_postal_code": "78701",
        "shipping_country": "US",
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
    assert "item_cogs" in data
    assert "gross_profit" in data
    assert "contribution_margin" in data
    assert data["shipping_recipient_name"] == "John Doe"
    assert data["shipping_label_ready"] is True


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
async def test_list_sales_exposes_channel_name_and_payment_method_for_pos_sales(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_product: Product
):
    payload = {
        "date": "2026-04-03",
        "payment_method": "cash",
        "items": [
            {
                "product_id": str(seed_product.id),
                "description": "Phone Stand",
                "quantity": 1,
                "unit_price": 8.99,
                "unit_cost": 3.50,
            }
        ],
    }
    create_resp = await client.post("/api/v1/pos/checkout", headers=auth_headers, json=payload)
    assert create_resp.status_code == 201

    pos_channel = (
        await db_session.execute(select(SalesChannel).where(SalesChannel.name == "POS"))
    ).scalar_one()
    resp = await client.get(
        "/api/v1/sales",
        params={"channel_id": str(pos_channel.id), "payment_method": "cash"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["channel_name"] == "POS"
    assert data["items"][0]["payment_method"] == "cash"


@pytest.mark.asyncio
async def test_get_sale(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/sales/{sale_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sale_id
    assert resp.json()["channel_name"] == "Direct"
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
async def test_get_shipping_label_returns_html_for_ready_sale(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/sales/{sale_id}/shipping-label", headers=auth_headers)

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "123 Maker Lane" in resp.text
    assert "S-2026-" in resp.text


@pytest.mark.asyncio
async def test_get_shipping_label_requires_shipping_fields(client: AsyncClient, auth_headers: dict):
    payload = _sale_payload()
    payload["shipping_address_line1"] = None
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=payload)
    sale_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/sales/{sale_id}/shipping-label", headers=auth_headers)

    assert resp.status_code == 409
    assert "address line 1" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_mark_shipping_label_printed_tracks_print_metadata(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/sales/{sale_id}/shipping-label/mark-printed",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["shipping_label_print_count"] == 1
    assert data["shipping_label_generated_at"] is not None
    assert data["shipping_label_last_printed_at"] is not None


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
    resp = await client.post(
        f"/api/v1/sales/{sale_id}/refund",
        headers=auth_headers,
        json={"reason": "Customer returned item"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_refund_already_refunded(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload())
    sale_id = create_resp.json()["id"]
    await client.post(
        f"/api/v1/sales/{sale_id}/refund",
        headers=auth_headers,
        json={"reason": "Customer returned item"},
    )
    resp = await client.post(
        f"/api/v1/sales/{sale_id}/refund",
        headers=auth_headers,
        json={"reason": "Duplicate refund attempt"},
    )
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
    assert data["gross_sales"] > 0
    assert data["gross_profit"] >= 0
    assert "platform_fees" in data
    assert "shipping_costs" in data
    assert "contribution_margin" in data
    assert "payment_method_breakdown" in data
    assert data["net_profit"] is None


@pytest.mark.asyncio
async def test_sale_metrics_can_filter_by_payment_method_and_channel(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_product: Product
):
    pos_payload = {
        "date": "2026-04-03",
        "payment_method": "cash",
        "items": [
            {
                "product_id": str(seed_product.id),
                "description": "Phone Stand",
                "quantity": 1,
                "unit_price": 8.99,
                "unit_cost": 3.50,
            }
        ],
    }
    pos_resp = await client.post("/api/v1/pos/checkout", headers=auth_headers, json=pos_payload)
    assert pos_resp.status_code == 201

    await client.post(
        "/api/v1/sales",
        headers=auth_headers,
        json={**_sale_payload(product_id=seed_product.id), "payment_method": "card"},
    )

    pos_channel = (
        await db_session.execute(select(SalesChannel).where(SalesChannel.name == "POS"))
    ).scalar_one()

    resp = await client.get(
        "/api/v1/sales/metrics",
        params={"channel_id": str(pos_channel.id), "payment_method": "cash"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sales"] == 1
    assert data["revenue_by_channel"][0]["channel_name"] == "POS"
    assert data["payment_method_breakdown"][0]["payment_method"] == "cash"


@pytest.mark.asyncio
async def test_sale_profit_layers_with_fees_and_shipping(client: AsyncClient, auth_headers: dict, seed_channel: SalesChannel):
    payload = _sale_payload(channel_id=seed_channel.id, shipping_cost=4.50, shipping_charged=5.00)
    resp = await client.post("/api/v1/sales", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert round(float(data["gross_profit"]), 2) == 15.98
    assert round(float(data["platform_fees"]), 2) == 1.37
    assert round(float(data["shipping_cost"]), 2) == 4.50
    assert round(float(data["contribution_margin"]), 2) == 10.11
