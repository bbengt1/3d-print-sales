from __future__ import annotations

from datetime import date, timedelta

import pytest


async def _seed_customer(client, auth_headers):
    resp = await client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={"name": "Wholesale Buyer", "email": "buyer@example.com"},
    )
    return resp.json()


def _invoice_payload(customer_id: str | None = None):
    issue_date = date.today() + timedelta(days=1)
    due_date = issue_date + timedelta(days=7)
    payload = {
        "invoice_number": "INV-2026-0001",
        "issue_date": issue_date.isoformat(),
        "due_date": due_date.isoformat(),
        "customer_name": "Wholesale Buyer",
        "tax_amount": "5.00",
        "shipping_amount": "10.00",
        "credits_applied": "0.00",
        "status": "sent",
        "lines": [
            {"description": "Batch of brackets", "quantity": 10, "unit_price": "12.50"}
        ],
    }
    if customer_id:
        payload["customer_id"] = customer_id
    return payload


def _quote_payload(material_id: str, customer_id: str | None = None):
    payload = {
        "quote_number": "Q-INV-0001",
        "date": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=14)).isoformat(),
        "customer_name": "Wholesale Buyer",
        "product_name": "Custom Bracket",
        "qty_per_plate": 2,
        "num_plates": 2,
        "material_id": material_id,
        "material_per_plate_g": "50.00",
        "print_time_per_plate_hrs": "2.00",
        "labor_mins": "15.00",
        "design_time_hrs": "0.50",
        "shipping_cost": "8.00",
        "target_margin_pct": "40.00",
        "status": "accepted",
    }
    if customer_id:
        payload["customer_id"] = customer_id
    return payload


@pytest.mark.asyncio
async def test_create_invoice_and_apply_partial_then_full_payment(client, auth_headers):
    customer = await _seed_customer(client, auth_headers)
    create_resp = await client.post("/api/v1/invoices", headers=auth_headers, json=_invoice_payload(customer["id"]))
    assert create_resp.status_code == 201
    invoice = create_resp.json()
    assert float(invoice["subtotal"]) == 125.0
    assert float(invoice["total_due"]) == 140.0
    assert float(invoice["balance_due"]) == 140.0
    assert invoice["status"] == "sent"

    partial = await client.post(
        f"/api/v1/invoices/{invoice['id']}/apply-payment",
        headers=auth_headers,
        json={"amount": "40.00", "paid_at": (date.today() + timedelta(days=2)).isoformat()},
    )
    assert partial.status_code == 200
    assert partial.json()["status"] == "partially_paid"
    assert float(partial.json()["balance_due"]) == 100.0

    full = await client.post(
        f"/api/v1/invoices/{invoice['id']}/apply-payment",
        headers=auth_headers,
        json={"amount": "100.00", "paid_at": (date.today() + timedelta(days=3)).isoformat()},
    )
    assert full.status_code == 200
    assert full.json()["status"] == "paid"
    assert float(full.json()["balance_due"]) == 0.0


@pytest.mark.asyncio
async def test_apply_credit_and_mark_invoice_paid(client, auth_headers):
    customer = await _seed_customer(client, auth_headers)
    create_resp = await client.post("/api/v1/invoices", headers=auth_headers, json=_invoice_payload(customer["id"]))
    invoice = create_resp.json()

    create_credit = await client.post(
        "/api/v1/invoices/credits",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "invoice_id": invoice["id"],
            "credit_date": (date.today() + timedelta(days=2)).isoformat(),
            "amount": "15.00",
            "reason": "Adjustment",
        },
    )
    assert create_credit.status_code == 201

    credit = await client.post(
        f"/api/v1/invoices/{invoice['id']}/apply-credit",
        headers=auth_headers,
        json={"amount": "15.00"},
    )
    assert credit.status_code == 200
    assert float(credit.json()["credits_applied"]) == 15.0
    assert float(credit.json()["balance_due"]) == 125.0

    payment = await client.post(
        f"/api/v1/invoices/{invoice['id']}/apply-payment",
        headers=auth_headers,
        json={"amount": "125.00"},
    )
    assert payment.status_code == 200
    assert payment.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_create_invoice_from_accepted_quote(client, auth_headers, seed_settings, seed_rates, seed_material):
    customer = await _seed_customer(client, auth_headers)
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json=_quote_payload(str(seed_material.id), customer_id=customer["id"]),
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()

    invoice_resp = await client.post(
        f"/api/v1/invoices/from-quote/{quote['id']}",
        headers=auth_headers,
        json={
            "invoice_number": "INV-QUOTE-0001",
            "issue_date": (date.today() + timedelta(days=1)).isoformat(),
            "due_date": (date.today() + timedelta(days=8)).isoformat(),
            "tax_amount": "4.00",
            "status": "sent",
        },
    )
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()
    assert invoice["quote_id"] == quote["id"]
    assert len(invoice["lines"]) == 1
    assert invoice["lines"][0]["description"] == "Custom Bracket"


@pytest.mark.asyncio
async def test_overdue_and_void_behavior(client, auth_headers):
    create_resp = await client.post("/api/v1/invoices", headers=auth_headers, json=_invoice_payload())
    invoice = create_resp.json()

    updated = await client.put(
        f"/api/v1/invoices/{invoice['id']}",
        headers=auth_headers,
        json={"due_date": "2026-03-01"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "overdue"

    voided = await client.put(
        f"/api/v1/invoices/{invoice['id']}",
        headers=auth_headers,
        json={"status": "void"},
    )
    assert voided.status_code == 200
    assert voided.json()["status"] == "void"

    pay_void = await client.post(
        f"/api/v1/invoices/{invoice['id']}/apply-payment",
        headers=auth_headers,
        json={"amount": "10.00"},
    )
    assert pay_void.status_code == 400
    assert "void invoice" in pay_void.json()["detail"].lower()
