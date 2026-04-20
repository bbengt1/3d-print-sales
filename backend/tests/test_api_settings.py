from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_settings(client, seed_settings, auth_headers):
    resp = await client.get("/api/v1/settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 17
    keys = {s["key"] for s in data}
    assert "currency" in keys
    assert "platform_fee_pct" in keys
    assert "ai_provider" in keys


@pytest.mark.asyncio
async def test_get_setting(client, seed_settings, auth_headers):
    resp = await client.get("/api/v1/settings/currency", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["value"] == "USD"


@pytest.mark.asyncio
async def test_get_setting_not_found(client, seed_settings, auth_headers):
    resp = await client.get("/api/v1/settings/nonexistent", headers=auth_headers)
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


@pytest.mark.asyncio
async def test_list_settings_requires_admin(client, seed_settings, user_headers):
    resp = await client.get("/api/v1/settings", headers=user_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_update_settings(client, seed_settings, auth_headers):
    """Regression: PUT /settings/bulk must hit the bulk handler (not /{key}).

    Previously the /{key} route was registered before /bulk, so POSTing to
    /settings/bulk matched with key="bulk" and validated against
    SettingUpdate (single-value schema), producing a "value: Field required"
    422 that the frontend couldn't explain to the user.
    """
    resp = await client.put(
        "/api/v1/settings/bulk",
        json={"settings": {"platform_fee_pct": "11.25", "currency": "EUR"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert isinstance(data, list)
    keys = {row["key"]: row["value"] for row in data}
    assert keys["platform_fee_pct"] == "11.25"
    assert keys["currency"] == "EUR"


@pytest.mark.asyncio
async def test_bulk_update_settings_requires_admin(client, seed_settings, user_headers):
    resp = await client.put(
        "/api/v1/settings/bulk",
        json={"settings": {"platform_fee_pct": "11.25"}},
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_update_settings_skips_unknown_keys(
    client, seed_settings, auth_headers
):
    """Unknown keys in the bulk payload are silently ignored (no 404)."""
    resp = await client.put(
        "/api/v1/settings/bulk",
        json={"settings": {"currency": "GBP", "some_unknown_key": "x"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.json()
    keys = {row["key"]: row["value"] for row in resp.json()}
    assert keys.get("currency") == "GBP"
    assert "some_unknown_key" not in keys
