from __future__ import annotations

import pytest


async def _create_job(client, seed_material, auth_headers, job_number, date="2026-03-01", product="Test"):
    return await client.post(
        "/api/v1/jobs",
        json={
            "job_number": job_number,
            "date": date,
            "product_name": product,
            "qty_per_plate": 2,
            "num_plates": 1,
            "material_id": str(seed_material.id),
            "material_per_plate_g": 45,
            "print_time_per_plate_hrs": 2.5,
        },
        headers=auth_headers,
    )


@pytest.mark.asyncio
async def test_summary_empty(client):
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_jobs"] == 0
    assert data["total_revenue"] == 0


@pytest.mark.asyncio
async def test_summary_with_jobs(client, seed_settings, seed_rates, seed_material, auth_headers):
    await _create_job(client, seed_material, auth_headers, "DASH-001")
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_jobs"] >= 1
    assert data["total_revenue"] > 0
    assert data["total_net_profit"] > 0


@pytest.mark.asyncio
async def test_summary_date_filter(client, seed_settings, seed_rates, seed_material, auth_headers):
    await _create_job(client, seed_material, auth_headers, "DASH-FEB", date="2026-02-15")
    resp = await client.get("/api/v1/dashboard/summary?date_from=2026-04-01&date_to=2026-04-30")
    assert resp.status_code == 200
    assert resp.json()["total_jobs"] == 0


@pytest.mark.asyncio
async def test_revenue_chart(client, seed_settings, seed_rates, seed_material, auth_headers):
    await _create_job(client, seed_material, auth_headers, "CHART-001")
    resp = await client.get("/api/v1/dashboard/charts/revenue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "date" in data[0]
    assert "revenue" in data[0]


@pytest.mark.asyncio
async def test_material_usage_chart(client, seed_settings, seed_rates, seed_material, auth_headers):
    await _create_job(client, seed_material, auth_headers, "MATC-001")
    resp = await client.get("/api/v1/dashboard/charts/materials")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["material"] == "PLA"


@pytest.mark.asyncio
async def test_profit_margin_chart(client, seed_settings, seed_rates, seed_material, auth_headers):
    await _create_job(client, seed_material, auth_headers, "PROF-001")
    resp = await client.get("/api/v1/dashboard/charts/profit-margins")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "margin" in data[0]
