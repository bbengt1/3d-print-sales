from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_rates(client, seed_rates):
    resp = await client.get("/api/v1/rates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_create_rate(client, auth_headers):
    resp = await client.post(
        "/api/v1/rates",
        json={"name": "Rush fee", "value": 15, "unit": "$/order", "notes": "Express"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Rush fee"


@pytest.mark.asyncio
async def test_create_rate_requires_auth(client):
    resp = await client.post(
        "/api/v1/rates",
        json={"name": "Rush fee", "value": 15, "unit": "$/order"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_rate_validation(client, auth_headers):
    resp = await client.post(
        "/api/v1/rates",
        json={"name": "", "value": -5, "unit": "$/hour"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_rate(client, seed_rates, auth_headers):
    rates = (await client.get("/api/v1/rates")).json()
    rate_id = rates[0]["id"]

    resp = await client.put(
        f"/api/v1/rates/{rate_id}", json={"value": 30}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert float(resp.json()["value"]) == 30


@pytest.mark.asyncio
async def test_delete_rate(client, seed_rates, auth_headers):
    rates = (await client.get("/api/v1/rates")).json()
    rate_id = rates[0]["id"]

    resp = await client.delete(f"/api/v1/rates/{rate_id}", headers=auth_headers)
    assert resp.status_code == 204
