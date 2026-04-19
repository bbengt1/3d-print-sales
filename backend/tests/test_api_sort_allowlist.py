"""Tests the sort_by / sort_dir query params added in issue #160 for the Sales, Products,
and Inventory endpoints. The allowlists are enforced by FastAPI's `Query(pattern=...)`
validation; anything outside the allowlist returns 422.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.material import Material
from app.models.product import Product


@pytest.mark.asyncio
async def test_sales_sort_allowlist_accepts_known_and_rejects_unknown(
    client: AsyncClient, auth_headers: dict, seed_settings, seed_material: Material
):
    # known sort columns succeed
    for col in ("date", "sale_number", "total", "status", "payment_method", "created_at"):
        resp = await client.get("/api/v1/sales", params={"sort_by": col, "sort_dir": "asc"})
        assert resp.status_code == 200, f"{col=} should be allowed"
    # unknown column is rejected
    resp = await client.get("/api/v1/sales", params={"sort_by": "secret_profit_field"})
    assert resp.status_code == 422

    # invalid direction is rejected
    resp = await client.get("/api/v1/sales", params={"sort_by": "date", "sort_dir": "sideways"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_products_sort_allowlist_accepts_known_and_rejects_unknown(
    client: AsyncClient, auth_headers: dict, seed_material: Material, db_session
):
    # Seed a couple of products so the sort actually runs against rows
    for i, (name, price, stock) in enumerate(
        [("Zulu widget", Decimal("10"), 1), ("Alpha widget", Decimal("20"), 5)]
    ):
        db_session.add(
            Product(
                sku=f"PRD-{i}",
                name=name,
                material_id=seed_material.id,
                unit_price=price,
                unit_cost=Decimal("1"),
                stock_qty=stock,
                reorder_point=0,
            )
        )
    await db_session.commit()

    for col in (
        "name",
        "sku",
        "unit_price",
        "unit_cost",
        "stock_qty",
        "reorder_point",
        "created_at",
        "updated_at",
    ):
        resp = await client.get(
            "/api/v1/products", params={"sort_by": col, "sort_dir": "desc"}
        )
        assert resp.status_code == 200, f"{col=} should be allowed"

    resp = await client.get("/api/v1/products", params={"sort_by": "drop_table"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_products_sort_actually_sorts(
    client: AsyncClient, auth_headers: dict, seed_material: Material, db_session
):
    # Two products, one with higher unit_price
    p_cheap = Product(
        sku="PRD-1",
        name="Cheap",
        material_id=seed_material.id,
        unit_price=Decimal("5"),
        unit_cost=Decimal("1"),
        stock_qty=0,
        reorder_point=0,
    )
    p_expensive = Product(
        sku="PRD-2",
        name="Expensive",
        material_id=seed_material.id,
        unit_price=Decimal("50"),
        unit_cost=Decimal("1"),
        stock_qty=0,
        reorder_point=0,
    )
    db_session.add_all([p_cheap, p_expensive])
    await db_session.commit()

    asc = await client.get("/api/v1/products", params={"sort_by": "unit_price", "sort_dir": "asc"})
    assert asc.status_code == 200
    asc_names = [p["name"] for p in asc.json()["items"]]
    assert asc_names.index("Cheap") < asc_names.index("Expensive")

    desc = await client.get("/api/v1/products", params={"sort_by": "unit_price", "sort_dir": "desc"})
    assert desc.status_code == 200
    desc_names = [p["name"] for p in desc.json()["items"]]
    assert desc_names.index("Expensive") < desc_names.index("Cheap")


@pytest.mark.asyncio
async def test_inventory_sort_allowlist_accepts_known_and_rejects_unknown(
    client: AsyncClient, auth_headers: dict, seed_material: Material
):
    for col in ("created_at", "type", "quantity", "unit_cost"):
        resp = await client.get(
            "/api/v1/inventory/transactions", params={"sort_by": col, "sort_dir": "asc"}
        )
        assert resp.status_code == 200, f"{col=} should be allowed"

    resp = await client.get(
        "/api/v1/inventory/transactions", params={"sort_by": "password_hash"}
    )
    assert resp.status_code == 422
