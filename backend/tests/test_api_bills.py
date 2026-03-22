from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.accounting_service import seed_chart_of_accounts


@pytest.mark.asyncio
async def test_create_bill_and_record_partial_then_full_payment(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)

    vendor = (await client.post(
        "/api/v1/accounting/vendors",
        headers=auth_headers,
        json={"name": "Polymaker", "is_active": True},
    )).json()
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    expense_account = next(a for a in accounts if a["code"] == "6000")
    category = (await client.post(
        "/api/v1/accounting/expense-categories",
        headers=auth_headers,
        json={
            "name": "Marketplace Ops",
            "description": "Marketplace-related expenses",
            "account_id": expense_account["id"],
            "is_active": True,
        },
    )).json()

    bill_resp = await client.post(
        "/api/v1/accounting/bills",
        headers=auth_headers,
        json={
            "vendor_id": vendor["id"],
            "expense_category_id": category["id"],
            "account_id": expense_account["id"],
            "bill_number": "BILL-1001",
            "description": "Marketplace monthly fees",
            "issue_date": "2026-03-22",
            "due_date": "2026-04-05",
            "amount": "100.00",
            "tax_amount": "0.00",
            "payment_method": "ach",
        },
    )
    assert bill_resp.status_code == 201
    bill = bill_resp.json()
    assert bill["status"] == "open"
    assert float(bill["amount_paid"]) == 0.0

    partial = await client.post(
        f"/api/v1/accounting/bills/{bill['id']}/payments",
        headers=auth_headers,
        json={
            "payment_date": "2026-03-23",
            "amount": "40.00",
            "payment_method": "ach",
            "reference_number": "PMT-1",
        },
    )
    assert partial.status_code == 201

    bills = (await client.get("/api/v1/accounting/bills", headers=auth_headers)).json()
    updated = next(b for b in bills if b["id"] == bill["id"])
    assert updated["status"] == "partially_paid"
    assert float(updated["amount_paid"]) == 40.0

    full = await client.post(
        f"/api/v1/accounting/bills/{bill['id']}/payments",
        headers=auth_headers,
        json={
            "payment_date": "2026-03-24",
            "amount": "60.00",
            "payment_method": "ach",
            "reference_number": "PMT-2",
        },
    )
    assert full.status_code == 201

    bills = (await client.get("/api/v1/accounting/bills", headers=auth_headers)).json()
    paid = next(b for b in bills if b["id"] == bill["id"])
    assert paid["status"] == "paid"
    assert float(paid["amount_paid"]) == 100.0
    assert len(paid["payments"]) == 2


@pytest.mark.asyncio
async def test_bill_payment_cannot_exceed_remaining_balance(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    expense_account = next(a for a in accounts if a["code"] == "6000")

    bill_resp = await client.post(
        "/api/v1/accounting/bills",
        headers=auth_headers,
        json={
            "account_id": expense_account["id"],
            "description": "Software subscription",
            "issue_date": "2026-03-22",
            "due_date": "2026-04-01",
            "amount": "50.00",
            "tax_amount": "0.00",
        },
    )
    bill = bill_resp.json()

    overpay = await client.post(
        f"/api/v1/accounting/bills/{bill['id']}/payments",
        headers=auth_headers,
        json={
            "payment_date": "2026-03-23",
            "amount": "60.00",
        },
    )
    assert overpay.status_code == 400
    assert "exceeds remaining balance" in overpay.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_admin_cannot_create_bill(client, user_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    accounts = (await client.get("/api/v1/accounting/accounts", headers={"Authorization": user_headers["Authorization"]})).json() if False else None
    # direct create should be blocked before account lookup matters
    resp = await client.post(
        "/api/v1/accounting/bills",
        headers=user_headers,
        json={
            "account_id": "00000000-0000-0000-0000-000000000000",
            "description": "Blocked",
            "issue_date": "2026-03-22",
            "amount": "10.00",
        },
    )
    assert resp.status_code == 403
