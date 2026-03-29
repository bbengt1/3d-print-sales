from __future__ import annotations

from datetime import datetime, timezone

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
    assert data["monitor_enabled"] is False


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


@pytest.mark.asyncio
async def test_refresh_printer_monitoring_endpoint_updates_live_fields(client: AsyncClient, auth_headers: dict, monkeypatch):
    async def fake_refresh(db, printer, force=False):
        printer.status = "printing"
        printer.monitor_online = True
        printer.monitor_status = "printing"
        printer.monitor_progress_percent = 42.5
        printer.current_print_name = "demo.gcode"
        printer.monitor_last_seen_at = datetime.now(timezone.utc)
        printer.monitor_last_updated_at = datetime.now(timezone.utc)
        return printer

    monkeypatch.setattr("app.api.v1.endpoints.printers.refresh_printer_monitoring", fake_refresh)

    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Octo Farm 1",
            "slug": "octo-farm-1",
            "status": "idle",
            "monitor_enabled": True,
            "monitor_provider": "octoprint",
            "monitor_base_url": "http://octoprint.local",
            "monitor_api_key": "secret",
        },
    )
    printer_id = create.json()["id"]

    resp = await client.post(f"/api/v1/printers/{printer_id}/refresh", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "printing"
    assert data["monitor_online"] is True
    assert data["monitor_progress_percent"] == 42.5
    assert data["current_print_name"] == "demo.gcode"


@pytest.mark.asyncio
async def test_test_connection_endpoint_returns_provider_result(client: AsyncClient, auth_headers: dict, monkeypatch):
    class FakeResult:
        ok = True
        provider = "octoprint"
        normalized_status = "idle"
        online = True
        message = "Connection successful"

    async def fake_test(printer):
        return FakeResult()

    monkeypatch.setattr("app.api.v1.endpoints.printers.test_printer_connection", fake_test)

    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Octo Farm 2",
            "slug": "octo-farm-2",
            "status": "idle",
            "monitor_enabled": True,
            "monitor_provider": "octoprint",
            "monitor_base_url": "http://octoprint.local",
        },
    )
    printer_id = create.json()["id"]

    resp = await client.post(f"/api/v1/printers/{printer_id}/test-connection", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "provider": "octoprint",
        "normalized_status": "idle",
        "online": True,
        "message": "Connection successful",
    }


@pytest.mark.asyncio
async def test_disabling_monitoring_clears_live_fields(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Octo Farm 3",
            "slug": "octo-farm-3",
            "status": "printing",
            "monitor_enabled": True,
            "monitor_provider": "octoprint",
            "monitor_base_url": "http://octoprint.local",
            "monitor_online": True,
        },
    )
    printer_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/printers/{printer_id}",
        headers=auth_headers,
        json={"monitor_enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["monitor_enabled"] is False
    assert data["monitor_online"] is None
    assert data["monitor_status"] is None
    assert data["monitor_progress_percent"] is None
    assert data["monitor_current_layer"] is None
    assert data["monitor_total_layers"] is None
    assert data["monitor_remaining_seconds"] is None
    assert data["monitor_ws_connected"] is None
