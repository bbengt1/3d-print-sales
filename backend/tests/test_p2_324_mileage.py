"""#324 P2: expense-claim mileage line type."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.expense_claim import ExpenseClaim, ExpenseClaimLine
from app.models.setting import Setting


async def _seed_minimum(db_session):
    obe = (await db_session.execute(select(Account).where(Account.code == "2300"))).scalar_one_or_none()
    if obe is None:
        db_session.add(Account(code="2300", name="Owner Reimb", account_type="liability", normal_balance="credit"))
    expense = (await db_session.execute(select(Account).where(Account.code == "6800"))).scalar_one_or_none()
    if expense is None:
        expense = Account(code="6800", name="Mileage", account_type="expense", normal_balance="debit")
        db_session.add(expense)
    await db_session.flush()
    return expense


@pytest.mark.asyncio
async def test_mileage_line_computes_amount(client: AsyncClient, auth_headers, db_session):
    expense = await _seed_minimum(db_session)
    db_session.add(Setting(key="expense_claims.mileage_rate_per_mile", value="0.67", notes=""))
    await db_session.commit()
    r = await client.post(
        "/api/v1/expense-claims",
        json={
            "payer_kind": "owner",
            "payer_name": "Brent",
            "lines": [
                {
                    "description": "Trip to vendor",
                    "expense_account_id": str(expense.id),
                    "line_kind": "mileage",
                    "miles": "120",
                }
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    # 120 * 0.67 = 80.40
    assert Decimal(body["total_amount"]) == Decimal("80.40")
    line = body["lines"][0]
    assert line["line_kind"] == "mileage"
    assert Decimal(line["miles"]) == Decimal("120")
    assert Decimal(line["mileage_rate_used"]) == Decimal("0.67")
    assert Decimal(line["amount"]) == Decimal("80.40")


@pytest.mark.asyncio
async def test_mileage_without_rate_setting_400(client: AsyncClient, auth_headers, db_session):
    expense = await _seed_minimum(db_session)
    await db_session.commit()
    r = await client.post(
        "/api/v1/expense-claims",
        json={
            "payer_kind": "owner",
            "payer_name": "Brent",
            "lines": [
                {"description": "Trip", "expense_account_id": str(expense.id),
                 "line_kind": "mileage", "miles": "10"}
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "mileage_rate_per_mile" in r.json()["detail"]


@pytest.mark.asyncio
async def test_expense_line_unaffected(client: AsyncClient, auth_headers, db_session):
    expense = await _seed_minimum(db_session)
    await db_session.commit()
    r = await client.post(
        "/api/v1/expense-claims",
        json={
            "payer_kind": "owner",
            "payer_name": "Brent",
            "lines": [
                {"description": "Coffee", "expense_account_id": str(expense.id), "amount": "12.50"}
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    line = body["lines"][0]
    assert line["line_kind"] == "expense"
    assert line["miles"] is None
    assert Decimal(line["amount"]) == Decimal("12.50")
