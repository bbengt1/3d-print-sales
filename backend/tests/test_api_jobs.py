from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_job(client, seed_settings, seed_rates, seed_material, auth_headers):
    resp = await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "TEST-001",
            "date": "2026-03-01",
            "product_name": "Phone Stand",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
            "labor_mins": 15,
            "design_time_hrs": 0.5,
            "shipping_cost": 0,
            "target_margin_pct": 40,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_number"] == "TEST-001"
    assert data["total_pieces"] == 1
    assert float(data["total_cost"]) > 0
    assert float(data["net_profit"]) > 0


@pytest.mark.asyncio
async def test_create_job_requires_auth(client, seed_settings, seed_rates, seed_material):
    resp = await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "NOAUTH-001",
            "date": "2026-03-01",
            "product_name": "Test",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_job_duplicate_number(client, seed_settings, seed_rates, seed_material, auth_headers):
    job_data = {
        "job_number": "DUP-001",
        "date": "2026-03-01",
        "product_name": "Test",
        "qty_per_plate": 1,
        "num_plates": 1,
        "material_id": str(seed_material.id),
        "material_per_plate_g": 45,
        "print_time_per_plate_hrs": 2.5,
    }
    await client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
    resp = await client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_job_validation(client, seed_settings, seed_rates, seed_material, auth_headers):
    resp = await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "",
            "date": "2026-03-01",
            "product_name": "Test",
            "qty_per_plate": 0,
            "num_plates": -1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
            "target_margin_pct": 150,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_jobs(client, seed_settings, seed_rates, seed_material, auth_headers):
    await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "LIST-001",
            "date": "2026-03-01",
            "product_name": "Item A",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_jobs_filter_by_search(client, seed_settings, seed_rates, seed_material, auth_headers):
    await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "SEARCH-001",
            "date": "2026-03-01",
            "product_name": "UniqueWidget",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/jobs?search=UniqueWidget")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["product_name"] == "UniqueWidget"


@pytest.mark.asyncio
async def test_list_jobs_filter_by_date(client, seed_settings, seed_rates, seed_material, auth_headers):
    await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "DATE-001",
            "date": "2026-01-15",
            "product_name": "Jan Item",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/jobs?date_from=2026-01-01&date_to=2026-01-31")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["date"].startswith("2026-01")


@pytest.mark.asyncio
async def test_get_job(client, seed_settings, seed_rates, seed_material, auth_headers):
    create_resp = await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "GET-001",
            "date": "2026-03-01",
            "product_name": "Get Test",
            "qty_per_plate": 2,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["product_name"] == "Get Test"
    assert resp.json()["total_pieces"] == 2


@pytest.mark.asyncio
async def test_update_job(client, seed_settings, seed_rates, seed_material, auth_headers):
    create_resp = await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "UPD-001",
            "date": "2026-03-01",
            "product_name": "Update Test",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )
    job_id = create_resp.json()["id"]
    original_cost = float(create_resp.json()["total_cost"])

    resp = await client.put(
        f"/api/v1/jobs/{job_id}",
        json={"num_plates": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total_pieces"] == 3
    assert float(resp.json()["total_cost"]) > original_cost


@pytest.mark.asyncio
async def test_delete_job(client, seed_settings, seed_rates, seed_material, auth_headers):
    create_resp = await client.post(
        "/api/v1/jobs",
        json={
            "job_number": "DEL-001",
            "date": "2026-03-01",
            "product_name": "Delete Test",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )
    job_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_calculate_preview(client, seed_settings, seed_rates, seed_material):
    resp = await client.post(
        "/api/v1/jobs/calculate",
        json={
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
            "labor_mins": 15,
            "design_time_hrs": 0.5,
            "shipping_cost": 0,
            "target_margin_pct": 40,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pieces"] == 1
    assert data["total_cost"] > 0
    assert data["net_profit"] > 0
