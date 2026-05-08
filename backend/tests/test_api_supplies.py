from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_supplies(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/supplies",
        headers=auth_headers,
        json={
            "name": "10x3mm magnet",
            "sku": "MAG-10X3",
            "category": "hardware",
            "unit": "each",
            "unit_cost": 0.18,
            "quantity_on_hand": 200,
            "reorder_point": 25,
            "supplier": "Parts Vendor",
        },
    )
    assert create.status_code == 201, create.text
    data = create.json()
    assert data["name"] == "10x3mm magnet"
    assert data["sku"] == "MAG-10X3"
    assert float(data["unit_cost"]) == pytest.approx(0.18)

    listed = await client.get("/api/v1/supplies", params={"search": "mag", "active": True})
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_supply_sku_must_be_unique(client: AsyncClient, auth_headers: dict):
    payload = {"name": "M3 screw", "sku": "SCREW-M3", "unit": "each", "unit_cost": 0.04}
    first = await client.post("/api/v1/supplies", headers=auth_headers, json=payload)
    assert first.status_code == 201
    duplicate = await client.post(
        "/api/v1/supplies",
        headers=auth_headers,
        json={**payload, "name": "M3 screw duplicate"},
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_adjust_supply_quantity(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/supplies",
        headers=auth_headers,
        json={"name": "LED strip", "unit": "m", "unit_cost": 3.5, "quantity_on_hand": 4},
    )
    supply_id = create.json()["id"]

    adjusted = await client.post(
        f"/api/v1/supplies/{supply_id}/adjust",
        headers=auth_headers,
        json={"quantity_delta": -1.5, "notes": "Used for demo sign"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert float(adjusted.json()["quantity_on_hand"]) == pytest.approx(2.5)

    rejected = await client.post(
        f"/api/v1/supplies/{supply_id}/adjust",
        headers=auth_headers,
        json={"quantity_delta": -3},
    )
    assert rejected.status_code == 400


@pytest.mark.asyncio
async def test_archive_supply(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/supplies",
        headers=auth_headers,
        json={"name": "Heat-set insert", "unit": "each", "unit_cost": 0.08, "quantity_on_hand": 100},
    )
    supply_id = create.json()["id"]

    deleted = await client.delete(f"/api/v1/supplies/{supply_id}", headers=auth_headers)
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/supplies/{supply_id}")
    assert fetched.status_code == 200
    assert fetched.json()["active"] is False
