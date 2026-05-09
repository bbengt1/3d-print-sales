from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account


async def _expense_account_id(db_session) -> str:
    a = (await db_session.execute(select(Account).where(Account.code == "6500"))).scalar_one()
    return str(a.id)


async def _asset_account_id(db_session) -> str:
    a = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    return str(a.id)


@pytest.mark.asyncio
async def test_upsert_creates_budget_rows(client: AsyncClient, auth_headers, db_session):
    aid = await _expense_account_id(db_session)
    resp = await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [{"account_id": aid, "year": 2026, "month": 1, "amount": "500"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["year"] == 2026
    assert data[0]["month"] == 1


@pytest.mark.asyncio
async def test_upsert_updates_existing(client: AsyncClient, auth_headers, db_session):
    aid = await _expense_account_id(db_session)
    await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [{"account_id": aid, "year": 2026, "month": 2, "amount": "100"}]},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [{"account_id": aid, "year": 2026, "month": 2, "amount": "250"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    list_resp = await client.get("/api/v1/budgets?year=2026", headers=auth_headers)
    rows = [r for r in list_resp.json() if r["month"] == 2]
    assert len(rows) == 1
    assert rows[0]["amount"] == "250.00"


@pytest.mark.asyncio
async def test_upsert_rejects_balance_sheet_account(client: AsyncClient, auth_headers, db_session):
    aid = await _asset_account_id(db_session)
    resp = await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [{"account_id": aid, "year": 2026, "month": 1, "amount": "500"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "income/expense" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_copy_year(client: AsyncClient, auth_headers, db_session):
    aid = await _expense_account_id(db_session)
    await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [
            {"account_id": aid, "year": 2026, "month": 1, "amount": "100"},
            {"account_id": aid, "year": 2026, "month": 2, "amount": "100"},
        ]},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/v1/budgets/copy-year?from_year=2026&to_year=2027",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["copied"] == 2
    assert body["skipped"] == 0


@pytest.mark.asyncio
async def test_copy_year_idempotent(client: AsyncClient, auth_headers, db_session):
    aid = await _expense_account_id(db_session)
    await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [{"account_id": aid, "year": 2026, "month": 3, "amount": "50"}]},
        headers=auth_headers,
    )
    await client.post("/api/v1/budgets/copy-year?from_year=2026&to_year=2027", headers=auth_headers)
    resp = await client.post("/api/v1/budgets/copy-year?from_year=2026&to_year=2027", headers=auth_headers)
    assert resp.json()["copied"] == 0
    assert resp.json()["skipped"] >= 1


@pytest.mark.asyncio
async def test_delete_budget(client: AsyncClient, auth_headers, db_session):
    aid = await _expense_account_id(db_session)
    create = await client.post(
        "/api/v1/budgets/upsert",
        json={"rows": [{"account_id": aid, "year": 2026, "month": 6, "amount": "75"}]},
        headers=auth_headers,
    )
    bid = create.json()[0]["id"]
    resp = await client.delete(f"/api/v1/budgets/{bid}", headers=auth_headers)
    assert resp.status_code == 204
