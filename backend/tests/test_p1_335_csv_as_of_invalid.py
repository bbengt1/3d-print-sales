"""#335 P1 (Codex): reject malformed `as_of` values supplied via CSV column.

Previously, when a row included an `as_of` cell, the endpoint called
``date.fromisoformat`` directly. A malformed value like ``2026/01/01`` raised
``ValueError`` and bubbled up as a 500. Validate it the same way the other
CSV field checks do and return a 400 instead.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account


async def _ensure_obe_and_account(db_session, code, name, account_type, normal_balance):
    obe = (
        await db_session.execute(select(Account).where(Account.code == "3300"))
    ).scalar_one_or_none()
    if obe is None:
        db_session.add(
            Account(
                code="3300",
                name="Opening Balance Equity",
                account_type="equity",
                normal_balance="credit",
            )
        )
    a = Account(code=code, name=name, account_type=account_type, normal_balance=normal_balance)
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_starting_balances_csv_rejects_malformed_as_of(
    client: AsyncClient, auth_headers, db_session
):
    await _ensure_obe_and_account(db_session, "1098", "Test Asset Bad", "asset", "debit")
    await db_session.commit()
    csv = b"account_code,amount,as_of\n1098,1500,2026/01/01\n"
    files = {"file": ("sb.csv", csv, "text/csv")}
    r = await client.post(
        "/api/v1/accounting/starting-balances.csv",
        files=files,
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "as_of" in detail
    assert "2026/01/01" in detail


@pytest.mark.asyncio
async def test_starting_balances_csv_accepts_valid_as_of(
    client: AsyncClient, auth_headers, db_session
):
    await _ensure_obe_and_account(db_session, "1097", "Test Asset Good", "asset", "debit")
    await db_session.commit()
    csv = b"account_code,amount,as_of\n1097,1500,2026-01-01\n"
    files = {"file": ("sb.csv", csv, "text/csv")}
    r = await client.post(
        "/api/v1/accounting/starting-balances.csv",
        files=files,
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_processed"] == 1
