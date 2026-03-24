from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.material import Material
from app.models.product import Product


@pytest_asyncio.fixture
async def seed_product(db_session: AsyncSession, seed_material: Material) -> Product:
    product = Product(
        sku="PRD-PLA-0001",
        name="Test Widget",
        material_id=seed_material.id,
        unit_cost=Decimal("3.50"),
        unit_price=Decimal("8.99"),
        stock_qty=10,
        reorder_point=5,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.mark.asyncio
async def test_create_stock_adjustment(
    client: AsyncClient, auth_headers: dict, seed_product: Product
):
    resp = await client.post(
        "/api/v1/inventory/transactions",
        headers=auth_headers,
        json={
            "product_id": str(seed_product.id),
            "type": "adjustment",
            "quantity": 5,
            "unit_cost": 3.50,
            "notes": "Received new batch",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "adjustment"
    assert data["quantity"] == 5

    # Verify stock updated
    prod_resp = await client.get(f"/api/v1/products/{seed_product.id}")
    assert prod_resp.json()["stock_qty"] == 15


@pytest.mark.asyncio
async def test_negative_stock_adjustment(
    client: AsyncClient, auth_headers: dict, seed_product: Product
):
    resp = await client.post(
        "/api/v1/inventory/transactions",
        headers=auth_headers,
        json={
            "product_id": str(seed_product.id),
            "type": "waste",
            "quantity": -3,
            "notes": "Defective items",
        },
    )
    assert resp.status_code == 201

    prod_resp = await client.get(f"/api/v1/products/{seed_product.id}")
    assert prod_resp.json()["stock_qty"] == 7


@pytest.mark.asyncio
async def test_transaction_requires_auth(client: AsyncClient, seed_product: Product):
    resp = await client.post(
        "/api/v1/inventory/transactions",
        json={
            "product_id": str(seed_product.id),
            "type": "adjustment",
            "quantity": 1,
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_transactions(
    client: AsyncClient, auth_headers: dict, seed_product: Product
):
    # Create two transactions
    for qty in [5, -2]:
        await client.post(
            "/api/v1/inventory/transactions",
            headers=auth_headers,
            json={
                "product_id": str(seed_product.id),
                "type": "adjustment",
                "quantity": qty,
                "notes": f"Adjustment {qty}",
            },
        )
    resp = await client.get(
        "/api/v1/inventory/transactions",
        params={"product_id": str(seed_product.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_transactions_supports_date_and_search_filters(
    client: AsyncClient, auth_headers: dict, seed_product: Product, db_session: AsyncSession
):
    first = await client.post(
        "/api/v1/inventory/transactions",
        headers=auth_headers,
        json={
            "product_id": str(seed_product.id),
            "type": "production",
            "quantity": 3,
            "notes": "Older production batch",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/inventory/transactions",
        headers=auth_headers,
        json={
            "product_id": str(seed_product.id),
            "type": "waste",
            "quantity": -1,
            "notes": "Recent waste",
        },
    )
    assert second.status_code == 201

    from app.models.inventory_transaction import InventoryTransaction

    first_txn = await db_session.get(InventoryTransaction, UUID(first.json()["id"]))
    second_txn = await db_session.get(InventoryTransaction, UUID(second.json()["id"]))
    first_txn.created_at = datetime.now(timezone.utc) - timedelta(days=3)
    second_txn.created_at = datetime.now(timezone.utc)
    await db_session.commit()

    search_resp = await client.get("/api/v1/inventory/transactions", params={"search": "Test Widget"})
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] >= 2
    assert search_data["items"][0]["product_name"] == "Test Widget"
    assert search_data["items"][0]["product_sku"] == "PRD-PLA-0001"

    type_resp = await client.get("/api/v1/inventory/transactions", params={"type": "production"})
    assert type_resp.status_code == 200
    assert all(item["type"] == "production" for item in type_resp.json()["items"])

    date_resp = await client.get(
        "/api/v1/inventory/transactions",
        params={"date_from": (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()},
    )
    assert date_resp.status_code == 200
    ids = {item["id"] for item in date_resp.json()["items"]}
    assert second.json()["id"] in ids
    assert first.json()["id"] not in ids


@pytest.mark.asyncio
async def test_alerts_low_stock_product(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_material: Material
):
    # Create product below reorder point
    product = Product(
        sku="PRD-PLA-9999",
        name="Low Stock Widget",
        material_id=seed_material.id,
        stock_qty=2,
        reorder_point=5,
    )
    db_session.add(product)
    await db_session.commit()

    resp = await client.get("/api/v1/inventory/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    product_alerts = [a for a in alerts if a["type"] == "product"]
    assert len(product_alerts) >= 1
    assert any(a["name"] == "Low Stock Widget" for a in product_alerts)


@pytest.mark.asyncio
async def test_alerts_low_stock_material(
    client: AsyncClient, db_session: AsyncSession, seed_material: Material
):
    # seed_material has spools_in_stock=0 and reorder_point=2 by default
    resp = await client.get("/api/v1/inventory/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    material_alerts = [a for a in alerts if a["type"] == "material"]
    assert len(material_alerts) >= 1


@pytest.mark.asyncio
async def test_job_auto_inventory(
    client: AsyncClient,
    auth_headers: dict,
    seed_material: Material,
    seed_settings,
    seed_rates,
    db_session: AsyncSession,
):
    # Create a product
    prod_resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Auto Stock Product", "material_id": str(seed_material.id)},
    )
    product_id = prod_resp.json()["id"]

    # Create a completed job linked to product
    job_resp = await client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={
            "job_number": "2026.3.20.001",
            "date": "2026-03-20",
            "product_name": "Auto Stock Product",
            "qty_per_plate": 4,
            "num_plates": 2,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
            "product_id": product_id,
            "status": "completed",
        },
    )
    assert job_resp.status_code == 201
    assert job_resp.json()["inventory_added"] is True

    # Verify product stock increased by total_pieces (4*2=8)
    prod_check = await client.get(f"/api/v1/products/{product_id}")
    assert prod_check.json()["stock_qty"] == 8


@pytest.mark.asyncio
async def test_reconcile_inventory_creates_adjustment(
    client: AsyncClient, auth_headers: dict, seed_product: Product
):
    resp = await client.post(
        "/api/v1/inventory/reconcile",
        headers=auth_headers,
        json={
            "product_id": str(seed_product.id),
            "counted_qty": 6,
            "reason": "Cycle count",
            "notes": "Back shelf recount",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_qty"] == 10
    assert data["counted_qty"] == 6
    assert data["variance"] == -4
    assert data["approval_required"] is False
    assert data["transaction"]["type"] == "adjustment"
    assert data["transaction"]["quantity"] == -4

    prod_resp = await client.get(f"/api/v1/products/{seed_product.id}")
    assert prod_resp.json()["stock_qty"] == 6


@pytest.mark.asyncio
async def test_reconcile_inventory_zero_variance_returns_noop(
    client: AsyncClient, auth_headers: dict, seed_product: Product
):
    resp = await client.post(
        "/api/v1/inventory/reconcile",
        headers=auth_headers,
        json={
            "product_id": str(seed_product.id),
            "counted_qty": 10,
            "reason": "Cycle count",
            "notes": "Matched shelf count",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["variance"] == 0
    assert data["transaction"] is None
