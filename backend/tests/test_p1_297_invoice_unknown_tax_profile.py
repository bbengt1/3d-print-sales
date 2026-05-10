"""Regression: Codex P1 on PR #297.

When `tax_profile_id` is provided with `tax_amount=0`, a typo or stale UUID
caused the invoice creation flow to silently leave tax at zero (because the
profile lookup returned no rows) instead of signaling a bad reference. The
create flow must raise 4xx and refuse to persist the invoice when
`tax_profile_id` is supplied but no profile is found.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models.invoice import Invoice


def _payload(customer_id: str, tax_profile_id: str):
    issue_date = date.today() + timedelta(days=1)
    due_date = issue_date + timedelta(days=7)
    return {
        "invoice_number": "INV-P1-297-0001",
        "issue_date": issue_date.isoformat(),
        "due_date": due_date.isoformat(),
        "customer_id": customer_id,
        "customer_name": "Wholesale Buyer",
        "tax_amount": "0.00",
        "tax_profile_id": tax_profile_id,
        "shipping_amount": "10.00",
        "credits_applied": "0.00",
        "status": "sent",
        "lines": [
            {"description": "Brackets", "quantity": 10, "unit_price": "12.50"},
        ],
    }


@pytest.mark.asyncio
async def test_create_invoice_with_unknown_tax_profile_rejected(
    client, auth_headers, db_session
):
    customer_resp = await client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json={"name": "Wholesale Buyer", "email": "buyer@example.com"},
    )
    assert customer_resp.status_code in (200, 201)
    customer_id = customer_resp.json()["id"]

    before = (
        await db_session.execute(select(func.count()).select_from(Invoice))
    ).scalar() or 0

    bogus_profile_id = str(uuid.uuid4())
    create_resp = await client.post(
        "/api/v1/invoices",
        headers=auth_headers,
        json=_payload(customer_id, bogus_profile_id),
    )

    assert 400 <= create_resp.status_code < 500, create_resp.text
    assert create_resp.status_code in (400, 404)

    after = (
        await db_session.execute(select(func.count()).select_from(Invoice))
    ).scalar() or 0
    assert after == before, "no invoice should be persisted on bad tax profile"
