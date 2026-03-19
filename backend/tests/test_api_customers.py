from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_customer(client):
    resp = await client.post(
        "/api/v1/customers",
        json={"name": "John Doe", "email": "john@example.com", "phone": "555-0100"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "John Doe"
    assert data["job_count"] == 0


@pytest.mark.asyncio
async def test_create_customer_validation(client):
    resp = await client.post(
        "/api/v1/customers",
        json={"name": "", "email": "not-an-email"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_customers(client):
    await client.post("/api/v1/customers", json={"name": "Alice"})
    await client.post("/api/v1/customers", json={"name": "Bob"})

    resp = await client.get("/api/v1/customers")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_search_customers(client):
    await client.post("/api/v1/customers", json={"name": "Unique Name XYZ"})
    resp = await client.get("/api/v1/customers?search=Unique")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert "Unique" in resp.json()[0]["name"]


@pytest.mark.asyncio
async def test_get_customer(client):
    create_resp = await client.post("/api/v1/customers", json={"name": "Get Test"})
    cid = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/customers/{cid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_update_customer(client):
    create_resp = await client.post("/api/v1/customers", json={"name": "Update Test"})
    cid = create_resp.json()["id"]

    resp = await client.put(f"/api/v1/customers/{cid}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_customer(client):
    create_resp = await client.post("/api/v1/customers", json={"name": "Delete Test"})
    cid = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/customers/{cid}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/customers/{cid}")
    assert resp.status_code == 404
