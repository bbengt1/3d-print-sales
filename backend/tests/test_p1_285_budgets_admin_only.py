"""Regression test for Codex P1 review on PR #285.

Budget mutating endpoints must require admin privileges. Non-admin
authenticated users were previously able to upsert/delete/copy budget
rows via the financial planning endpoints.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account


async def _expense_account_id(db_session) -> str:
    a = (
        await db_session.execute(select(Account).where(Account.code == "6500"))
    ).scalar_one()
    return str(a.id)


# ---------------------------------------------------------------------------
# Non-admin users get 403 on every mutating endpoint.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_admin_cannot_upsert_budgets(
    client: AsyncClient, user_headers, db_session
):
    aid = await _expense_account_id(db_session)
    resp = await client.post(
        "/api/v1/budgets/upsert",
        json={
            "rows": [
                {"account_id": aid, "year": 2026, "month": 1, "amount": "500"}
            ]
        },
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_delete_budget(
    client: AsyncClient, auth_headers, user_headers, db_session
):
    # Admin seeds a row first so the delete target exists.
    aid = await _expense_account_id(db_session)
    create = await client.post(
        "/api/v1/budgets/upsert",
        json={
            "rows": [
                {"account_id": aid, "year": 2026, "month": 6, "amount": "75"}
            ]
        },
        headers=auth_headers,
    )
    assert create.status_code == 200
    bid = create.json()[0]["id"]

    resp = await client.delete(f"/api/v1/budgets/{bid}", headers=user_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_copy_year(client: AsyncClient, user_headers):
    resp = await client.post(
        "/api/v1/budgets/copy-year?from_year=2026&to_year=2027",
        headers=user_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Read endpoints remain accessible to regular users.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_admin_can_list_budgets(client: AsyncClient, user_headers):
    resp = await client.get("/api/v1/budgets", headers=user_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Admins still pass the auth gate for mutations.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_upsert_budgets(
    client: AsyncClient, auth_headers, db_session
):
    aid = await _expense_account_id(db_session)
    resp = await client.post(
        "/api/v1/budgets/upsert",
        json={
            "rows": [
                {"account_id": aid, "year": 2026, "month": 1, "amount": "500"}
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_copy_year(
    client: AsyncClient, auth_headers, db_session
):
    aid = await _expense_account_id(db_session)
    seed = await client.post(
        "/api/v1/budgets/upsert",
        json={
            "rows": [
                {"account_id": aid, "year": 2026, "month": 1, "amount": "100"}
            ]
        },
        headers=auth_headers,
    )
    assert seed.status_code == 200
    resp = await client.post(
        "/api/v1/budgets/copy-year?from_year=2026&to_year=2027",
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_delete_budget(
    client: AsyncClient, auth_headers, db_session
):
    aid = await _expense_account_id(db_session)
    create = await client.post(
        "/api/v1/budgets/upsert",
        json={
            "rows": [
                {"account_id": aid, "year": 2026, "month": 6, "amount": "75"}
            ]
        },
        headers=auth_headers,
    )
    assert create.status_code == 200
    bid = create.json()[0]["id"]
    resp = await client.delete(
        f"/api/v1/budgets/{bid}", headers=auth_headers
    )
    assert resp.status_code == 204
