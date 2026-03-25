from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_printer(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Bambu X1C",
            "slug": "bambu-x1c-01",
            "manufacturer": "Bambu Lab",
            "model": "X1 Carbon",
            "location": "Print Room",
            "status": "idle",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Bambu X1C"
    assert data["slug"] == "bambu-x1c-01"
    assert data["status"] == "idle"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_printer_rejects_duplicate_name_or_slug(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "Prusa MK4",
        "slug": "prusa-mk4-01",
        "manufacturer": "Prusa",
        "model": "MK4",
    }
    first = await client.post("/api/v1/printers", headers=auth_headers, json=payload)
    assert first.status_code == 201

    dup_name = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={**payload, "slug": "prusa-mk4-02"},
    )
    assert dup_name.status_code == 409

    dup_slug = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={**payload, "name": "Prusa MK4 Copy"},
    )
    assert dup_slug.status_code == 409


@pytest.mark.asyncio
async def test_update_printer_status(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={"name": "Voron 2.4", "slug": "voron-24-01", "status": "idle"},
    )
    printer_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/printers/{printer_id}",
        headers=auth_headers,
        json={"status": "maintenance", "location": "Bench A"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "maintenance"
    assert data["location"] == "Bench A"


@pytest.mark.asyncio
async def test_list_and_get_printers(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={"name": "P1S", "slug": "p1s-01", "status": "printing"},
    )
    await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={"name": "K1 Max", "slug": "k1-max-01", "status": "idle", "location": "Garage"},
    )

    list_resp = await client.get("/api/v1/printers", params={"status": "idle", "search": "Garage"})
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    printer_id = data["items"][0]["id"]

    get_resp = await client.get(f"/api/v1/printers/{printer_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "K1 Max"


@pytest.mark.asyncio
async def test_delete_printer_soft_deactivates(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={"name": "Ender 3", "slug": "ender-3-01", "status": "offline"},
    )
    printer_id = create.json()["id"]

    delete_resp = await client.delete(f"/api/v1/printers/{printer_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/printers/{printer_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False
