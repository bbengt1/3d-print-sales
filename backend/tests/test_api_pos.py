from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale
from app.models.sales_channel import SalesChannel


@pytest_asyncio.fixture
async def seed_pos_product(db_session: AsyncSession, seed_material) -> Product:
    product = Product(
        name="Desk Dragon",
        sku="POS-DRAGON-001",
        material_id=seed_material.id,
        unit_price=Decimal("15.00"),
        unit_cost=Decimal("6.00"),
        stock_qty=5,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest_asyncio.fixture
async def seed_customer(db_session: AsyncSession) -> Customer:
    customer = Customer(name="Morgan Buyer", email="morgan@example.com")
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@pytest_asyncio.fixture
async def seed_low_stock_product(db_session: AsyncSession, seed_material) -> Product:
    product = Product(
        name="Mini Wyvern",
        sku="POS-WYVERN-001",
        material_id=seed_material.id,
        unit_price=Decimal("12.00"),
        unit_cost=Decimal("5.00"),
        stock_qty=1,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


def _payload(product_id, **overrides):
    quantity = overrides.pop("quantity", 2)
    payload = {
        "date": "2026-04-03",
        "payment_method": "cash",
        "items": [
            {
                "product_id": str(product_id),
                "description": "Desk Dragon",
                "quantity": quantity,
                "unit_price": 15,
                "unit_cost": 6,
            }
        ],
    }
    payload.update(overrides)
    return payload


async def _create_scannable_product(
    db_session: AsyncSession,
    *,
    material_id,
    sku: str,
    name: str,
    upc: str,
    stock_qty: int = 5,
    is_active: bool = True,
) -> Product:
    product = Product(
        sku=sku,
        name=name,
        material_id=material_id,
        unit_price=10,
        unit_cost=4,
        stock_qty=stock_qty,
        reorder_point=1,
        is_active=is_active,
        upc=upc,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.mark.asyncio
async def test_pos_checkout_guest_sale_uses_pos_channel_and_deducts_inventory(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    seed_pos_product: Product,
):
    resp = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json=_payload(seed_pos_product.id, customer_name="Walk-up Customer", notes="Booth checkout"),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "paid"
    assert data["customer_id"] is None
    assert data["customer_name"] == "Walk-up Customer"
    assert data["payment_method"] == "cash"
    assert float(data["total"]) == 30.0

    sale = (
        await db_session.execute(select(Sale).where(Sale.id == uuid.UUID(data["id"])))
    ).scalar_one()
    channel = (
        await db_session.execute(select(SalesChannel).where(SalesChannel.id == sale.channel_id))
    ).scalar_one()
    assert channel.name == "POS"

    product_resp = await client.get(f"/api/v1/products/{seed_pos_product.id}")
    assert product_resp.status_code == 200
    assert product_resp.json()["stock_qty"] == 3


@pytest.mark.asyncio
async def test_pos_checkout_customer_linked_sale_defaults_customer_name(
    client: AsyncClient,
    auth_headers: dict,
    seed_pos_product: Product,
    seed_customer: Customer,
):
    resp = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json=_payload(seed_pos_product.id, customer_id=str(seed_customer.id), payment_method="card"),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["customer_id"] == str(seed_customer.id)
    assert data["customer_name"] == seed_customer.name
    assert data["payment_method"] == "card"
    assert float(data["platform_fees"]) == 0.0


@pytest.mark.asyncio
async def test_pos_checkout_rejects_unknown_customer(
    client: AsyncClient,
    auth_headers: dict,
    seed_pos_product: Product,
):
    resp = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json=_payload(
            seed_pos_product.id,
            customer_id="00000000-0000-0000-0000-000000000000",
        ),
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Customer not found"


@pytest.mark.asyncio
async def test_pos_checkout_blocks_insufficient_stock_without_creating_sale_or_inventory_transactions(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    seed_pos_product: Product,
):
    resp = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json=_payload(seed_pos_product.id, quantity=6),
    )

    assert resp.status_code == 409
    assert "Insufficient stock for POS checkout" in resp.json()["detail"]

    product_resp = await client.get(f"/api/v1/products/{seed_pos_product.id}")
    assert product_resp.status_code == 200
    assert product_resp.json()["stock_qty"] == 5

    sale_count = (await db_session.execute(select(Sale))).scalars().all()
    txn_count = (await db_session.execute(select(InventoryTransaction))).scalars().all()
    assert sale_count == []
    assert txn_count == []


@pytest.mark.asyncio
async def test_pos_checkout_is_all_or_nothing_when_one_line_item_is_short_on_stock(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    seed_pos_product: Product,
    seed_low_stock_product: Product,
):
    resp = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "date": "2026-04-03",
            "payment_method": "cash",
            "items": [
                {
                    "product_id": str(seed_pos_product.id),
                    "description": "Desk Dragon",
                    "quantity": 2,
                    "unit_price": 15,
                    "unit_cost": 6,
                },
                {
                    "product_id": str(seed_low_stock_product.id),
                    "description": "Mini Wyvern",
                    "quantity": 2,
                    "unit_price": 12,
                    "unit_cost": 5,
                },
            ],
        },
    )

    assert resp.status_code == 409
    assert seed_low_stock_product.name in resp.json()["detail"]

    first_product_resp = await client.get(f"/api/v1/products/{seed_pos_product.id}")
    second_product_resp = await client.get(f"/api/v1/products/{seed_low_stock_product.id}")
    assert first_product_resp.json()["stock_qty"] == 5
    assert second_product_resp.json()["stock_qty"] == 1

    sale_count = (await db_session.execute(select(Sale))).scalars().all()
    txn_count = (await db_session.execute(select(InventoryTransaction))).scalars().all()
    assert sale_count == []
    assert txn_count == []


@pytest.mark.asyncio
async def test_pos_refund_restores_inventory_for_pos_sale(
    client: AsyncClient,
    auth_headers: dict,
    seed_pos_product: Product,
):
    create_resp = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json=_payload(seed_pos_product.id, quantity=2),
    )
    assert create_resp.status_code == 201
    sale_id = create_resp.json()["id"]

    refund_resp = await client.post(
        f"/api/v1/sales/{sale_id}/refund",
        headers=auth_headers,
        json={"reason": "Customer changed mind"},
    )
    assert refund_resp.status_code == 200
    assert refund_resp.json()["status"] == "refunded"

    product_resp = await client.get(f"/api/v1/products/{seed_pos_product.id}")
    assert product_resp.status_code == 200
    assert product_resp.json()["stock_qty"] == 5


@pytest.mark.asyncio
async def test_pos_scan_resolves_active_product(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_material):
    product = await _create_scannable_product(
        db_session,
        material_id=seed_material.id,
        sku="PRD-PLA-9001",
        name="Desk Dragon",
        upc="012345678901",
    )

    resp = await client.post("/api/v1/pos/scan/resolve", headers=auth_headers, json={"code": "012345678901"})
    assert resp.status_code == 200
    assert resp.json()["id"] == str(product.id)
    assert resp.json()["name"] == "Desk Dragon"


@pytest.mark.asyncio
async def test_pos_scan_rejects_unknown_barcode(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/pos/scan/resolve", headers=auth_headers, json={"code": "000000000000"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pos_scan_rejects_inactive_product(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_material):
    await _create_scannable_product(
        db_session,
        material_id=seed_material.id,
        sku="PRD-PLA-9002",
        name="Inactive Dragon",
        upc="123450000000",
        is_active=False,
    )

    resp = await client.post("/api/v1/pos/scan/resolve", headers=auth_headers, json={"code": "123450000000"})
    assert resp.status_code == 409
    assert "inactive product" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pos_scan_rejects_out_of_stock_product(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, seed_material):
    await _create_scannable_product(
        db_session,
        material_id=seed_material.id,
        sku="PRD-PLA-9003",
        name="Sold Out Dragon",
        upc="999990000000",
        stock_qty=0,
    )

    resp = await client.post("/api/v1/pos/scan/resolve", headers=auth_headers, json={"code": "999990000000"})
    assert resp.status_code == 409
    assert "out of stock" in resp.json()["detail"].lower()
