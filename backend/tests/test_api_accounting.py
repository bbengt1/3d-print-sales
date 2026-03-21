from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.accounting_service import ensure_accounting_period, seed_chart_of_accounts


@pytest.mark.asyncio
async def test_list_accounts_admin_only(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)

    resp = await client.get("/api/v1/accounting/accounts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 20
    assert any(row["code"] == "1000" for row in data)


@pytest.mark.asyncio
async def test_create_account_and_update_parent(client, auth_headers, db_session: AsyncSession):
    parent_resp = await client.post(
        "/api/v1/accounting/accounts",
        headers=auth_headers,
        json={
            "code": "7000",
            "name": "Operating Expenses",
            "account_type": "expense",
            "normal_balance": "debit",
            "description": "Parent expense bucket",
            "is_active": True,
        },
    )
    assert parent_resp.status_code == 201
    parent = parent_resp.json()

    child_resp = await client.post(
        "/api/v1/accounting/accounts",
        headers=auth_headers,
        json={
            "code": "7010",
            "name": "Shop Supplies",
            "account_type": "expense",
            "normal_balance": "debit",
            "description": "Consumables and small tools",
            "is_active": True,
        },
    )
    assert child_resp.status_code == 201
    child = child_resp.json()

    update_resp = await client.put(
        f"/api/v1/accounting/accounts/{child['id']}",
        headers=auth_headers,
        json={"parent_id": parent["id"], "is_active": False},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["parent_id"] == parent["id"]
    assert updated["is_active"] is False


@pytest.mark.asyncio
async def test_create_duplicate_account_code_returns_409(client, auth_headers):
    payload = {
        "code": "7001",
        "name": "Test Expense",
        "account_type": "expense",
        "normal_balance": "debit",
        "is_active": True,
    }
    first = await client.post("/api/v1/accounting/accounts", headers=auth_headers, json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/accounting/accounts", headers=auth_headers, json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_list_accounts_forbidden_for_non_admin(client, user_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    resp = await client.get("/api/v1/accounting/accounts", headers=user_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_periods(client, auth_headers, db_session: AsyncSession):
    await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    resp = await client.get("/api/v1/accounting/periods", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["period_key"] == "2026-03"


@pytest.mark.asyncio
async def test_create_period_update_status_and_reject_duplicate_key(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/accounting/periods",
        headers=auth_headers,
        json={
            "period_key": "2026-04",
            "name": "April 2026",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "status": "open",
            "is_adjustment_period": False,
        },
    )
    assert create_resp.status_code == 201
    period = create_resp.json()

    update_resp = await client.put(
        f"/api/v1/accounting/periods/{period['id']}",
        headers=auth_headers,
        json={"status": "closed", "is_adjustment_period": True},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "closed"
    assert updated["is_adjustment_period"] is True

    dup_resp = await client.post(
        "/api/v1/accounting/periods",
        headers=auth_headers,
        json={
            "period_key": "2026-04",
            "name": "April 2026 Duplicate",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "status": "open",
            "is_adjustment_period": False,
        },
    )
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_create_and_get_journal_entry(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")

    payload = {
        "entry_date": "2026-03-21",
        "accounting_period_id": str(period.id),
        "source_type": "sale",
        "source_id": "S-2026-0001",
        "memo": "Record direct sale",
        "lines": [
            {"account_id": cash["id"], "entry_type": "debit", "amount": "25.00"},
            {"account_id": sales["id"], "entry_type": "credit", "amount": "25.00"},
        ],
    }

    resp = await client.post("/api/v1/accounting/journal-entries", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "posted"
    assert len(data["lines"]) == 2

    get_resp = await client.get(f"/api/v1/accounting/journal-entries/{data['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == data["id"]


@pytest.mark.asyncio
async def test_create_unbalanced_journal_entry_returns_400(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")

    payload = {
        "entry_date": "2026-03-21",
        "accounting_period_id": str(period.id),
        "lines": [
            {"account_id": cash["id"], "entry_type": "debit", "amount": "30.00"},
            {"account_id": sales["id"], "entry_type": "credit", "amount": "25.00"},
        ],
    }

    resp = await client.post("/api/v1/accounting/journal-entries", headers=auth_headers, json=payload)
    assert resp.status_code == 400
    assert "unbalanced" in resp.json()["detail"].lower()
