from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.accounting_service import seed_chart_of_accounts


@pytest.mark.asyncio
async def test_create_and_list_vendor(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/accounting/vendors",
        headers=auth_headers,
        json={
            "name": "MatterHackers",
            "contact_name": "Sales Team",
            "email": "sales@example.com",
            "phone": "555-1000",
            "notes": "Primary filament supplier",
            "is_active": True,
        },
    )
    assert create_resp.status_code == 201
    vendor = create_resp.json()
    assert vendor["name"] == "MatterHackers"

    list_resp = await client.get("/api/v1/accounting/vendors", headers=auth_headers)
    assert list_resp.status_code == 200
    vendors = list_resp.json()
    assert any(v["name"] == "MatterHackers" for v in vendors)


@pytest.mark.asyncio
async def test_create_and_update_expense_category(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    expense_account = next(a for a in accounts if a["code"] == "6000")
    cogs_account = next(a for a in accounts if a["code"] == "5000")

    create_resp = await client.post(
        "/api/v1/accounting/expense-categories",
        headers=auth_headers,
        json={
            "name": "Marketplace Fees",
            "description": "Fees charged by online platforms",
            "account_id": expense_account["id"],
            "is_active": True,
        },
    )
    assert create_resp.status_code == 201
    category = create_resp.json()
    assert category["name"] == "Marketplace Fees"

    update_resp = await client.put(
        f"/api/v1/accounting/expense-categories/{category['id']}",
        headers=auth_headers,
        json={"account_id": cogs_account["id"], "is_active": False},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["account_id"] == cogs_account["id"]
    assert updated["is_active"] is False


@pytest.mark.asyncio
async def test_expense_category_rejects_non_expense_account(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    asset_account = next(a for a in accounts if a["code"] == "1000")

    resp = await client.post(
        "/api/v1/accounting/expense-categories",
        headers=auth_headers,
        json={
            "name": "Bad Mapping",
            "description": "Should fail",
            "account_id": asset_account["id"],
            "is_active": True,
        },
    )
    assert resp.status_code == 400
    assert "expense or cogs account" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_admin_cannot_create_vendor(client, user_headers):
    resp = await client.post(
        "/api/v1/accounting/vendors",
        headers=user_headers,
        json={"name": "Blocked Vendor", "is_active": True},
    )
    assert resp.status_code == 403
