from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_customer(client, auth_headers):
    resp = await client.post(
        "/api/v1/customers",
        json={"name": "John Doe", "email": "john@example.com", "phone": "555-0100"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "John Doe"
    assert data["job_count"] == 0


@pytest.mark.asyncio
async def test_create_customer_requires_auth(client):
    resp = await client.post(
        "/api/v1/customers", json={"name": "No Auth"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_customer_validation(client, auth_headers):
    resp = await client.post(
        "/api/v1/customers",
        json={"name": "", "email": "not-an-email"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_customers(client, auth_headers):
    await client.post("/api/v1/customers", json={"name": "Alice"}, headers=auth_headers)
    await client.post("/api/v1/customers", json={"name": "Bob"}, headers=auth_headers)

    resp = await client.get("/api/v1/customers")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_search_customers(client, auth_headers):
    await client.post(
        "/api/v1/customers",
        json={"name": "Unique Name XYZ"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/customers?search=Unique")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert "Unique" in resp.json()[0]["name"]


@pytest.mark.asyncio
async def test_get_customer(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/customers", json={"name": "Get Test"}, headers=auth_headers
    )
    cid = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/customers/{cid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_update_customer(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/customers", json={"name": "Update Test"}, headers=auth_headers
    )
    cid = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/customers/{cid}",
        json={"name": "Updated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_customer(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/customers", json={"name": "Delete Test"}, headers=auth_headers
    )
    cid = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/customers/{cid}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/customers/{cid}")
    assert resp.status_code == 404
