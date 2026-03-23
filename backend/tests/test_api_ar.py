from __future__ import annotations

import pytest


async def _seed_customer(client, auth_headers):
    resp = await client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={"name": "AR Customer", "email": "ar@example.com"},
    )
    return resp.json()


def _invoice_payload(customer_id: str):
    return {
        "invoice_number": "INV-AR-0001",
        "customer_id": customer_id,
        "customer_name": "AR Customer",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-15",
        "tax_amount": "0.00",
        "shipping_amount": "0.00",
        "status": "sent",
        "lines": [{"description": "Fixture run", "quantity": 1, "unit_price": "100.00"}],
    }


@pytest.mark.asyncio
async def test_record_payment_with_unapplied_cash(client, auth_headers):
    customer = await _seed_customer(client, auth_headers)
    create_resp = await client.post("/api/v1/invoices", headers=auth_headers, json=_invoice_payload(customer["id"]))
    invoice = create_resp.json()

    payment_resp = await client.post(
        "/api/v1/invoices/payments",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "invoice_id": invoice["id"],
            "payment_date": "2026-03-20",
            "amount": "120.00",
            "payment_method": "ach",
        },
    )
    assert payment_resp.status_code == 201
    payment = payment_resp.json()
    assert float(payment["unapplied_amount"]) == 20.0

    invoice_resp = await client.get(f"/api/v1/invoices/{invoice['id']}")
    assert invoice_resp.status_code == 200
    assert invoice_resp.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_create_customer_credit_and_apply_to_invoice(client, auth_headers):
    customer = await _seed_customer(client, auth_headers)
    create_resp = await client.post("/api/v1/invoices", headers=auth_headers, json=_invoice_payload(customer["id"]))
    invoice = create_resp.json()

    credit_resp = await client.post(
        "/api/v1/invoices/credits",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "invoice_id": invoice["id"],
            "credit_date": "2026-03-18",
            "amount": "30.00",
            "reason": "Courtesy adjustment",
        },
    )
    assert credit_resp.status_code == 201

    apply_resp = await client.post(
        f"/api/v1/invoices/{invoice['id']}/apply-credit",
        headers=auth_headers,
        json={"amount": "30.00"},
    )
    assert apply_resp.status_code == 200
    assert float(apply_resp.json()["credits_applied"]) == 30.0
    assert float(apply_resp.json()["balance_due"]) == 70.0


@pytest.mark.asyncio
async def test_ar_aging_report_buckets(client, auth_headers):
    customer = await _seed_customer(client, auth_headers)

    inv1 = _invoice_payload(customer["id"])
    inv1["invoice_number"] = "INV-AR-CURRENT"
    inv1["due_date"] = "2026-03-30"
    await client.post("/api/v1/invoices", headers=auth_headers, json=inv1)

    inv2 = _invoice_payload(customer["id"])
    inv2["invoice_number"] = "INV-AR-31-60"
    inv2["due_date"] = "2026-02-15"
    await client.post("/api/v1/invoices", headers=auth_headers, json=inv2)

    inv3 = _invoice_payload(customer["id"])
    inv3["invoice_number"] = "INV-AR-90P"
    inv3["due_date"] = "2025-12-01"
    await client.post("/api/v1/invoices", headers=auth_headers, json=inv3)

    report_resp = await client.get("/api/v1/invoices/reports/ar-aging", headers=auth_headers, params={"as_of_date": "2026-03-23"})
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert float(report["current_total"]) == 100.0
    assert float(report["bucket_31_60_total"]) == 100.0
    assert float(report["bucket_90_plus_total"]) == 100.0
    assert float(report["total_outstanding"]) == 300.0
