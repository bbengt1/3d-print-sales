from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
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


def _payload(product_id, **overrides):
    payload = {
        "date": "2026-04-03",
        "payment_method": "cash",
        "items": [
            {
                "product_id": str(product_id),
                "description": "Desk Dragon",
                "quantity": 2,
                "unit_price": 15,
                "unit_cost": 6,
            }
        ],
    }
    payload.update(overrides)
    return payload


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
