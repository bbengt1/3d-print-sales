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
async def test_create_material(client):
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
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "PETG"
    assert float(data["cost_per_g"]) == pytest.approx(24 / 950, rel=1e-3)


@pytest.mark.asyncio
async def test_create_material_validation(client):
    resp = await client.post(
        "/api/v1/materials",
        json={
            "name": "",
            "brand": "Generic",
            "spool_weight_g": -1,
            "spool_price": 20,
            "net_usable_g": 950,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_material(client, seed_material):
    resp = await client.get(f"/api/v1/materials/{seed_material.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "PLA"


@pytest.mark.asyncio
async def test_update_material(client, seed_material):
    resp = await client.put(
        f"/api/v1/materials/{seed_material.id}",
        json={"spool_price": 25},
    )
    assert resp.status_code == 200
    assert float(resp.json()["spool_price"]) == 25


@pytest.mark.asyncio
async def test_delete_material(client, seed_material):
    resp = await client.delete(f"/api/v1/materials/{seed_material.id}")
    assert resp.status_code == 204

    # Should still exist but inactive
    resp = await client.get(f"/api/v1/materials/{seed_material.id}")
    assert resp.status_code == 200
    assert resp.json()["active"] is False
