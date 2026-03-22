from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_materials(client, seed_material):
    resp = await client.get("/api/v1/materials")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "PLA"


@pytest.mark.asyncio
async def test_list_materials_filter_active(client, seed_material):
    resp = await client.get("/api/v1/materials?active=true")
    assert resp.status_code == 200
    assert all(m["active"] for m in resp.json())


@pytest.mark.asyncio
async def test_list_materials_search(client, seed_material):
    resp = await client.get("/api/v1/materials?search=pla")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_create_material(client, auth_headers):
    resp = await client.post(
        "/api/v1/materials",
        json={
            "name": "PETG",
            "brand": "Generic",
            "spool_weight_g": 1000,
            "spool_price": 24,
            "net_usable_g": 950,
            "notes": "Stronger",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "PETG"
    assert float(data["cost_per_g"]) == pytest.approx(24 / 950, rel=1e-3)


@pytest.mark.asyncio
async def test_create_material_requires_auth(client):
    resp = await client.post(
        "/api/v1/materials",
        json={
            "name": "PETG",
            "brand": "Generic",
            "spool_weight_g": 1000,
            "spool_price": 24,
            "net_usable_g": 950,
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_material_validation(client, auth_headers):
    resp = await client.post(
        "/api/v1/materials",
        json={
            "name": "",
            "brand": "Generic",
            "spool_weight_g": -1,
            "spool_price": 20,
            "net_usable_g": 950,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_material(client, seed_material):
    resp = await client.get(f"/api/v1/materials/{seed_material.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "PLA"


@pytest.mark.asyncio
async def test_update_material(client, seed_material, auth_headers):
    resp = await client.put(
        f"/api/v1/materials/{seed_material.id}",
        json={"spool_price": 25},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert float(resp.json()["spool_price"]) == 25


@pytest.mark.asyncio
async def test_create_and_list_material_receipts(client, seed_material, auth_headers):
    create_resp = await client.post(
        f"/api/v1/materials/{seed_material.id}/receipts",
        json={
            "vendor_name": "MatterHackers",
            "purchase_date": "2026-03-22",
            "receipt_number": "PO-1001",
            "quantity_purchased_g": "1000",
            "unit_cost_per_g": "0.020000",
            "landed_cost_total": "5.00",
            "valuation_method": "lot",
            "notes": "Initial stocked spool",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert float(created["landed_cost_per_g"]) == pytest.approx(0.005, rel=1e-5)
    assert float(created["total_cost"]) == pytest.approx(25.0, rel=1e-5)
    assert float(created["quantity_remaining_g"]) == pytest.approx(1000.0, rel=1e-5)

    list_resp = await client.get(f"/api/v1/materials/{seed_material.id}/receipts")
    assert list_resp.status_code == 200
    receipts = list_resp.json()
    assert len(receipts) == 1
    assert receipts[0]["vendor_name"] == "MatterHackers"

    material_resp = await client.get(f"/api/v1/materials/{seed_material.id}")
    assert material_resp.status_code == 200
    assert float(material_resp.json()["cost_per_g"]) == pytest.approx(0.025, rel=1e-5)


@pytest.mark.asyncio
async def test_delete_material(client, seed_material, auth_headers):
    resp = await client.delete(
        f"/api/v1/materials/{seed_material.id}", headers=auth_headers
    )
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/materials/{seed_material.id}")
    assert resp.status_code == 200
    assert resp.json()["active"] is False
