from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_division(client: AsyncClient, auth_headers):
    resp = await client.post("/api/v1/divisions", json={"name": "Wholesale"}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Wholesale"
    assert body["is_active"] is True

    resp = await client.get("/api/v1/divisions", headers=auth_headers)
    assert resp.status_code == 200
    assert any(d["name"] == "Wholesale" for d in resp.json())


@pytest.mark.asyncio
async def test_division_unique_name(client: AsyncClient, auth_headers):
    await client.post("/api/v1/divisions", json={"name": "Marketplace"}, headers=auth_headers)
    resp = await client.post("/api/v1/divisions", json={"name": "Marketplace"}, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_division_deactivate_hides_from_default_list(client: AsyncClient, auth_headers):
    resp = await client.post("/api/v1/divisions", json={"name": "Old"}, headers=auth_headers)
    div_id = resp.json()["id"]
    await client.patch(f"/api/v1/divisions/{div_id}", json={"is_active": False}, headers=auth_headers)
    default_list = await client.get("/api/v1/divisions", headers=auth_headers)
    assert all(d["name"] != "Old" for d in default_list.json())
    full_list = await client.get("/api/v1/divisions?include_inactive=true", headers=auth_headers)
    assert any(d["name"] == "Old" for d in full_list.json())


@pytest.mark.asyncio
async def test_division_delete(client: AsyncClient, auth_headers):
    resp = await client.post("/api/v1/divisions", json={"name": "TempDel"}, headers=auth_headers)
    div_id = resp.json()["id"]
    resp = await client.delete(f"/api/v1/divisions/{div_id}", headers=auth_headers)
    assert resp.status_code == 204
    resp = await client.get("/api/v1/divisions?include_inactive=true", headers=auth_headers)
    assert all(d["id"] != div_id for d in resp.json())


@pytest.mark.asyncio
async def test_create_and_list_project(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Custom Commission Q2", "start_on": "2026-04-01"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Custom Commission Q2"
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_project_archive_filters(client: AsyncClient, auth_headers):
    resp = await client.post("/api/v1/projects", json={"name": "Old promo"}, headers=auth_headers)
    pid = resp.json()["id"]
    await client.patch(f"/api/v1/projects/{pid}", json={"status": "archived"}, headers=auth_headers)
    default = await client.get("/api/v1/projects", headers=auth_headers)
    assert all(p["name"] != "Old promo" for p in default.json())
    full = await client.get("/api/v1/projects?include_archived=true", headers=auth_headers)
    assert any(p["name"] == "Old promo" for p in full.json())
