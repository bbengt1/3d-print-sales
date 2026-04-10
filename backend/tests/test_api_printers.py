from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.printer import Printer
from app.models.printer_history_event import PrinterHistoryEvent


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
    assert "monitor_api_key" not in data
    assert data["monitor_api_key_configured"] is True


@pytest.mark.asyncio
async def test_printer_responses_do_not_expose_monitor_api_key(client: AsyncClient, auth_headers: dict, monkeypatch):
    async def fake_refresh(db, printer, force=False):
        return printer

    monkeypatch.setattr("app.api.v1.endpoints.printers.refresh_printer_monitoring", fake_refresh)

    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Secret Safe Printer",
            "slug": "secret-safe-printer",
            "status": "idle",
            "monitor_enabled": True,
            "monitor_provider": "octoprint",
            "monitor_base_url": "http://octoprint.local",
            "monitor_api_key": "super-secret-key",
        },
    )
    assert create.status_code == 201
    created = create.json()
    assert "monitor_api_key" not in created
    assert created["monitor_api_key_configured"] is True

    printer_id = created["id"]
    detail = await client.get(f"/api/v1/printers/{printer_id}")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert "monitor_api_key" not in detail_data
    assert detail_data["monitor_api_key_configured"] is True

    listing = await client.get("/api/v1/printers")
    assert listing.status_code == 200
    list_item = next(item for item in listing.json()["items"] if item["id"] == printer_id)
    assert "monitor_api_key" not in list_item
    assert list_item["monitor_api_key_configured"] is True


@pytest.mark.asyncio
async def test_update_printer_can_clear_saved_monitor_api_key(client: AsyncClient, auth_headers: dict, db_session):
    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Clearable Secret Printer",
            "slug": "clearable-secret-printer",
            "status": "idle",
            "monitor_enabled": True,
            "monitor_provider": "octoprint",
            "monitor_base_url": "http://octoprint.local",
            "monitor_api_key": "super-secret-key",
        },
    )
    printer_id = create.json()["id"]

    clear = await client.put(
        f"/api/v1/printers/{printer_id}",
        headers=auth_headers,
        json={"clear_monitor_api_key": True},
    )
    assert clear.status_code == 200
    data = clear.json()
    assert "monitor_api_key" not in data
    assert data["monitor_api_key_configured"] is False
    stored = await db_session.scalar(select(Printer).where(Printer.id == uuid.UUID(printer_id)))
    assert stored is not None
    assert stored.monitor_api_key is None


@pytest.mark.asyncio
async def test_disabling_monitoring_clears_saved_monitor_api_key(client: AsyncClient, auth_headers: dict, db_session):
    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={
            "name": "Disable Monitoring Secret Printer",
            "slug": "disable-monitoring-secret-printer",
            "status": "printing",
            "monitor_enabled": True,
            "monitor_provider": "octoprint",
            "monitor_base_url": "http://octoprint.local",
            "monitor_api_key": "super-secret-key",
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
    assert data["monitor_api_key_configured"] is False
    stored = await db_session.scalar(select(Printer).where(Printer.id == uuid.UUID(printer_id)))
    assert stored is not None
    assert stored.monitor_api_key is None


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


@pytest.mark.asyncio
async def test_update_printer_status_records_history_event(client: AsyncClient, auth_headers: dict, db_session):
    create = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={"name": "History Printer", "slug": "history-printer", "status": "idle"},
    )
    printer_id = create.json()["id"]

    update = await client.put(
        f"/api/v1/printers/{printer_id}",
        headers=auth_headers,
        json={"status": "printing"},
    )
    assert update.status_code == 200
    assert update.json()["history_events"] == []

    events = (await db_session.execute(select(PrinterHistoryEvent).where(PrinterHistoryEvent.printer_id == uuid.UUID(printer_id)))).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "status_changed"
    assert events[0].event_metadata["from_status"] == "idle"
    assert events[0].event_metadata["to_status"] == "printing"

    detail = await client.get(f"/api/v1/printers/{printer_id}")
    assert detail.status_code == 200
    history = detail.json()["history_events"]
    assert len(history) == 1
    assert history[0]["event_type"] == "status_changed"
    assert history[0]["actor_name"]
