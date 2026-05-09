from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.customer import Customer
from app.models.vendor import Vendor


@pytest.mark.asyncio
async def test_create_sales_order_assigns_number(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="X", email="x@y.z")
    db_session.add(c)
    await db_session.commit()
    resp = await client.post(
        "/api/v1/sales-orders",
        json={
            "customer_id": str(c.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "Widget", "quantity": "5", "unit_price": "10"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sales_order_number"].startswith("SO-")
    assert body["status"] == "draft"
    assert body["total_amount"] == "50.00"


@pytest.mark.asyncio
async def test_sales_order_requires_customer_or_name(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/v1/sales-orders",
        json={
            "issue_date": "2026-05-01",
            "lines": [{"description": "X", "quantity": "1", "unit_price": "1"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_sales_order(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="Y", email="y@z.q")
    db_session.add(c)
    await db_session.commit()
    create = await client.post(
        "/api/v1/sales-orders",
        json={
            "customer_id": str(c.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "X", "quantity": "1", "unit_price": "10"}],
        },
        headers=auth_headers,
    )
    so_id = create.json()["id"]
    resp = await client.post(f"/api/v1/sales-orders/{so_id}/confirm", headers=auth_headers)
    assert resp.json()["status"] == "confirmed"
    # Cannot confirm again
    resp2 = await client.post(f"/api/v1/sales-orders/{so_id}/confirm", headers=auth_headers)
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_cancel_sales_order(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="Z", email="z@a.b")
    db_session.add(c)
    await db_session.commit()
    create = await client.post(
        "/api/v1/sales-orders",
        json={
            "customer_id": str(c.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "X", "quantity": "1", "unit_price": "5"}],
        },
        headers=auth_headers,
    )
    so_id = create.json()["id"]
    resp = await client.post(f"/api/v1/sales-orders/{so_id}/cancel", headers=auth_headers)
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_create_purchase_order(client: AsyncClient, auth_headers, db_session):
    v = Vendor(name="V")
    db_session.add(v)
    await db_session.commit()
    resp = await client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": str(v.id),
            "issue_date": "2026-05-01",
            "lines": [
                {"description": "Filament", "quantity": "10", "unit_price": "20"},
                {"description": "Boxes", "quantity": "100", "unit_price": "0.50"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["purchase_order_number"].startswith("PO-")
    assert body["total_amount"] == "250.00"


@pytest.mark.asyncio
async def test_confirm_purchase_order(client: AsyncClient, auth_headers, db_session):
    v = Vendor(name="V2")
    db_session.add(v)
    await db_session.commit()
    create = await client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": str(v.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "x", "quantity": "1", "unit_price": "5"}],
        },
        headers=auth_headers,
    )
    po_id = create.json()["id"]
    resp = await client.post(f"/api/v1/purchase-orders/{po_id}/confirm", headers=auth_headers)
    assert resp.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_purchase_order_detail_includes_lines(client: AsyncClient, auth_headers, db_session):
    v = Vendor(name="V3")
    db_session.add(v)
    await db_session.commit()
    create = await client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": str(v.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "lineA", "quantity": "2", "unit_price": "3"}],
        },
        headers=auth_headers,
    )
    po_id = create.json()["id"]
    resp = await client.get(f"/api/v1/purchase-orders/{po_id}", headers=auth_headers)
    body = resp.json()
    assert len(body["lines"]) == 1
    assert body["lines"][0]["description"] == "lineA"
