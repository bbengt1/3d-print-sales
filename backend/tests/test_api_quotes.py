from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_customer(client, auth_headers):
    resp = await client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={"name": "Acme Prototype Lab", "email": "lab@example.com"},
    )
    return resp.json()


def _quote_payload(material_id: str, customer_id: str | None = None):
    payload = {
        "quote_number": "Q-2026-0001",
        "date": "2026-03-23",
        "valid_until": "2026-04-06",
        "customer_name": "Acme Prototype Lab",
        "product_name": "Custom Jig",
        "qty_per_plate": 2,
        "num_plates": 3,
        "material_id": material_id,
        "material_per_plate_g": "80.00",
        "print_time_per_plate_hrs": "4.50",
        "labor_mins": "30.00",
        "design_time_hrs": "1.50",
        "shipping_cost": "12.00",
        "target_margin_pct": "45.00",
        "status": "draft",
    }
    if customer_id:
        payload["customer_id"] = customer_id
    return payload


@pytest.mark.asyncio
async def test_create_quote_and_recalculate_values(client, auth_headers, seed_settings, seed_rates, seed_material):
    payload = _quote_payload(str(seed_material.id))
    resp = await client.post("/api/v1/quotes", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["quote_number"] == "Q-2026-0001"
    assert data["status"] == "draft"
    assert data["total_pieces"] == 6
    assert float(data["total_cost"]) > 0
    assert float(data["total_revenue"]) > float(data["total_cost"])


@pytest.mark.asyncio
async def test_update_quote_status_and_fields(client, auth_headers, seed_settings, seed_rates, seed_material):
    create_resp = await client.post("/api/v1/quotes", headers=auth_headers, json=_quote_payload(str(seed_material.id)))
    quote_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/quotes/{quote_id}",
        headers=auth_headers,
        json={"status": "sent", "shipping_cost": "18.00"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert float(data["shipping_cost"]) == 18.0


@pytest.mark.asyncio
async def test_convert_accepted_quote_to_job(client, auth_headers, seed_settings, seed_rates, seed_material):
    customer = await _seed_customer(client, auth_headers)
    create_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json=_quote_payload(str(seed_material.id), customer_id=customer["id"]),
    )
    quote_id = create_resp.json()["id"]

    accept_resp = await client.put(
        f"/api/v1/quotes/{quote_id}",
        headers=auth_headers,
        json={"status": "accepted"},
    )
    assert accept_resp.status_code == 200

    convert_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/convert-to-job",
        headers=auth_headers,
        json={"job_number": "JOB-QUOTE-001", "job_date": "2026-03-24", "status": "draft"},
    )
    assert convert_resp.status_code == 200
    data = convert_resp.json()
    assert data["job_number"] == "JOB-QUOTE-001"

    job_resp = await client.get(f"/api/v1/jobs/{data['job_id']}")
    assert job_resp.status_code == 200
    assert job_resp.json()["product_name"] == "Custom Jig"


@pytest.mark.asyncio
async def test_cannot_convert_unaccepted_quote(client, auth_headers, seed_settings, seed_rates, seed_material):
    create_resp = await client.post("/api/v1/quotes", headers=auth_headers, json=_quote_payload(str(seed_material.id)))
    quote_id = create_resp.json()["id"]

    convert_resp = await client.post(
        f"/api/v1/quotes/{quote_id}/convert-to-job",
        headers=auth_headers,
        json={"job_number": "JOB-QUOTE-002"},
    )
    assert convert_resp.status_code == 400
    assert "accepted quotes" in convert_resp.json()["detail"].lower()
