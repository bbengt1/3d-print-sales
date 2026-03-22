from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.accounting_service import seed_chart_of_accounts


@pytest.mark.asyncio
async def test_create_recurring_expense_generate_bill_and_report(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)

    vendor = (await client.post(
        "/api/v1/accounting/vendors",
        headers=auth_headers,
        json={"name": "AWS", "is_active": True},
    )).json()
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    expense_account = next(a for a in accounts if a["code"] == "6100")
    category = (await client.post(
        "/api/v1/accounting/expense-categories",
        headers=auth_headers,
        json={
            "name": "Cloud Hosting",
            "description": "Cloud services",
            "account_id": expense_account["id"],
            "is_active": True,
        },
    )).json()

    recurring_resp = await client.post(
        "/api/v1/accounting/recurring-expenses",
        headers=auth_headers,
        json={
            "vendor_id": vendor["id"],
            "expense_category_id": category["id"],
            "account_id": expense_account["id"],
            "description": "Monthly hosting bill",
            "amount": "29.99",
            "tax_amount": "0.00",
            "frequency": "monthly",
            "next_due_date": "2026-03-22",
            "payment_method": "card",
            "is_active": True,
        },
    )
    assert recurring_resp.status_code == 201
    recurring = recurring_resp.json()

    generate_resp = await client.post(
        f"/api/v1/accounting/recurring-expenses/{recurring['id']}/generate",
        headers=auth_headers,
        json={"as_of_date": "2026-03-22"},
    )
    assert generate_resp.status_code == 201
    bill = generate_resp.json()
    assert bill["description"] == "Monthly hosting bill"
    assert bill["status"] == "open"

    category_report = await client.get("/api/v1/accounting/reports/expenses/by-category", headers=auth_headers)
    assert category_report.status_code == 200
    assert any(r["label"] == "Cloud Hosting" for r in category_report.json())

    vendor_report = await client.get("/api/v1/accounting/reports/expenses/by-vendor", headers=auth_headers)
    assert vendor_report.status_code == 200
    assert any(r["label"] == "AWS" for r in vendor_report.json())


@pytest.mark.asyncio
async def test_recurring_expense_cannot_generate_before_due_date(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    expense_account = next(a for a in accounts if a["code"] == "6100")

    recurring_resp = await client.post(
        "/api/v1/accounting/recurring-expenses",
        headers=auth_headers,
        json={
            "account_id": expense_account["id"],
            "description": "Future subscription",
            "amount": "10.00",
            "tax_amount": "0.00",
            "frequency": "monthly",
            "next_due_date": "2026-04-01",
            "is_active": True,
        },
    )
    recurring = recurring_resp.json()

    generate_resp = await client.post(
        f"/api/v1/accounting/recurring-expenses/{recurring['id']}/generate",
        headers=auth_headers,
        json={"as_of_date": "2026-03-22"},
    )
    assert generate_resp.status_code == 400
    assert "not due yet" in generate_resp.json()["detail"].lower()
