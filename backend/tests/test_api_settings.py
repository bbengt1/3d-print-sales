from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_settings(client, seed_settings):
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    keys = {s["key"] for s in data}
    assert "currency" in keys
    assert "platform_fee_pct" in keys


@pytest.mark.asyncio
async def test_get_setting(client, seed_settings):
    resp = await client.get("/api/v1/settings/currency")
    assert resp.status_code == 200
    assert resp.json()["value"] == "USD"


@pytest.mark.asyncio
async def test_get_setting_not_found(client, seed_settings):
    resp = await client.get("/api/v1/settings/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_setting(client, seed_settings, auth_headers):
    resp = await client.put(
        "/api/v1/settings/platform_fee_pct",
        json={"value": "12.5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "12.5"


@pytest.mark.asyncio
async def test_update_setting_validation(client, seed_settings, auth_headers):
    resp = await client.put(
        "/api/v1/settings/currency",
        json={"value": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_setting_requires_admin(client, seed_settings, user_headers):
    resp = await client.put(
        "/api/v1/settings/currency",
        json={"value": "EUR"},
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_setting_requires_auth(client, seed_settings):
    resp = await client.put(
        "/api/v1/settings/currency", json={"value": "EUR"}
    )
    assert resp.status_code == 401
