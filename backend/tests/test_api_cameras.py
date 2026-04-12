from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _create_printer(client: AsyncClient, auth_headers: dict, name: str, slug: str) -> dict:
    resp = await client.post(
        "/api/v1/printers",
        headers=auth_headers,
        json={"name": name, "slug": slug, "status": "idle"},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_camera(
    client: AsyncClient,
    auth_headers: dict,
    name: str = "Wyze Cam 1",
    slug: str = "wyze-cam-1",
    printer_id: str | None = None,
) -> dict:
    payload = {
        "name": name,
        "slug": slug,
        "go2rtc_base_url": "http://192.168.1.50:1984",
        "stream_name": "wyze_printer_1",
    }
    if printer_id:
        payload["printer_id"] = printer_id
    resp = await client.post("/api/v1/cameras", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_camera(client: AsyncClient, auth_headers: dict):
    data = await _create_camera(client, auth_headers)
    assert data["name"] == "Wyze Cam 1"
    assert data["slug"] == "wyze-cam-1"
    assert data["go2rtc_base_url"] == "http://192.168.1.50:1984"
    assert data["stream_name"] == "wyze_printer_1"
    assert data["printer_id"] is None
    assert data["is_active"] is True
    assert data["snapshot_url"].startswith("/api/v1/cameras/")
    assert "ws://" in data["mse_ws_url"]


@pytest.mark.asyncio
async def test_create_camera_rejects_duplicate_name_or_slug(client: AsyncClient, auth_headers: dict):
    await _create_camera(client, auth_headers)

    dup_name = await client.post(
        "/api/v1/cameras",
        headers=auth_headers,
        json={
            "name": "Wyze Cam 1",
            "slug": "wyze-cam-1-other",
            "go2rtc_base_url": "http://192.168.1.50:1984",
            "stream_name": "other",
        },
    )
    assert dup_name.status_code == 409

    dup_slug = await client.post(
        "/api/v1/cameras",
        headers=auth_headers,
        json={
            "name": "Other Cam",
            "slug": "wyze-cam-1",
            "go2rtc_base_url": "http://192.168.1.50:1984",
            "stream_name": "other",
        },
    )
    assert dup_slug.status_code == 409


@pytest.mark.asyncio
async def test_create_camera_with_printer_assignment(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "Bambu X1C", "bambu-x1c")
    camera = await _create_camera(client, auth_headers, printer_id=printer["id"])
    assert camera["printer_id"] == printer["id"]
    assert camera["printer_name"] == "Bambu X1C"


@pytest.mark.asyncio
async def test_create_camera_rejects_duplicate_printer_assignment(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "Prusa MK4", "prusa-mk4")
    await _create_camera(client, auth_headers, printer_id=printer["id"])

    dup = await client.post(
        "/api/v1/cameras",
        headers=auth_headers,
        json={
            "name": "Cam 2",
            "slug": "cam-2",
            "go2rtc_base_url": "http://192.168.1.50:1984",
            "stream_name": "cam2",
            "printer_id": printer["id"],
        },
    )
    assert dup.status_code == 409
    assert "already has a camera" in dup.json()["detail"]


@pytest.mark.asyncio
async def test_update_camera(client: AsyncClient, auth_headers: dict):
    camera = await _create_camera(client, auth_headers)
    resp = await client.put(
        f"/api/v1/cameras/{camera['id']}",
        headers=auth_headers,
        json={"name": "Wyze Cam Updated", "stream_name": "wyze_updated"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Wyze Cam Updated"
    assert data["stream_name"] == "wyze_updated"


@pytest.mark.asyncio
async def test_assign_and_unassign_camera(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "Voron 2.4", "voron-24")
    camera = await _create_camera(client, auth_headers)

    # Assign
    assign = await client.post(
        f"/api/v1/cameras/{camera['id']}/assign",
        headers=auth_headers,
        json={"printer_id": printer["id"]},
    )
    assert assign.status_code == 200
    assert assign.json()["printer_id"] == printer["id"]

    # Unassign
    unassign = await client.post(
        f"/api/v1/cameras/{camera['id']}/assign",
        headers=auth_headers,
        json={"printer_id": None},
    )
    assert unassign.status_code == 200
    assert unassign.json()["printer_id"] is None


@pytest.mark.asyncio
async def test_reassign_camera_between_printers(client: AsyncClient, auth_headers: dict):
    p1 = await _create_printer(client, auth_headers, "Printer A", "printer-a")
    p2 = await _create_printer(client, auth_headers, "Printer B", "printer-b")
    camera = await _create_camera(client, auth_headers, printer_id=p1["id"])

    # Reassign to printer B
    resp = await client.post(
        f"/api/v1/cameras/{camera['id']}/assign",
        headers=auth_headers,
        json={"printer_id": p2["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["printer_id"] == p2["id"]
    assert resp.json()["printer_name"] == "Printer B"


@pytest.mark.asyncio
async def test_delete_camera_soft_deactivates_and_unassigns(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "Ender 3", "ender-3")
    camera = await _create_camera(client, auth_headers, printer_id=printer["id"])

    delete_resp = await client.delete(f"/api/v1/cameras/{camera['id']}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/cameras/{camera['id']}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["is_active"] is False
    assert data["printer_id"] is None


@pytest.mark.asyncio
async def test_list_cameras_with_filters(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "P1S", "p1s")
    await _create_camera(client, auth_headers, name="Assigned Cam", slug="assigned-cam", printer_id=printer["id"])
    await _create_camera(client, auth_headers, name="Free Cam", slug="free-cam")

    # All cameras
    all_resp = await client.get("/api/v1/cameras")
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 2

    # Assigned only
    assigned_resp = await client.get("/api/v1/cameras", params={"assigned": True})
    assert assigned_resp.json()["total"] == 1
    assert assigned_resp.json()["items"][0]["name"] == "Assigned Cam"

    # Unassigned only
    free_resp = await client.get("/api/v1/cameras", params={"assigned": False})
    assert free_resp.json()["total"] == 1
    assert free_resp.json()["items"][0]["name"] == "Free Cam"

    # Search
    search_resp = await client.get("/api/v1/cameras", params={"search": "Free"})
    assert search_resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_snapshot_returns_404_for_missing_camera(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/cameras/{fake_id}/snapshot")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_printer_response_includes_camera_data(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "Cam Printer", "cam-printer")
    camera = await _create_camera(client, auth_headers, printer_id=printer["id"])

    # Get printer should include camera fields
    get_resp = await client.get(f"/api/v1/printers/{printer['id']}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["camera_id"] == camera["id"]
    assert data["camera_name"] == "Wyze Cam 1"
    assert data["camera_snapshot_url"].startswith("/api/v1/cameras/")
    assert "ws://" in data["camera_mse_ws_url"]


@pytest.mark.asyncio
async def test_printer_response_without_camera_has_null_fields(client: AsyncClient, auth_headers: dict):
    printer = await _create_printer(client, auth_headers, "No Cam", "no-cam")
    get_resp = await client.get(f"/api/v1/printers/{printer['id']}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["camera_id"] is None
    assert data["camera_name"] is None
    assert data["camera_snapshot_url"] is None
    assert data["camera_mse_ws_url"] is None
