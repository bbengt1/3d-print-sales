"""#278 P1 (Codex): expense claim with non-existent expense_account_id must
return a 4xx client error instead of a 500 from a foreign-key violation, and
must not leave a partial claim row behind.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.expense_claim import ExpenseClaim


@pytest.mark.asyncio
async def test_create_claim_invalid_expense_account_returns_404(
    client: AsyncClient, auth_headers, db_session
):
    bogus_account_id = uuid.uuid4()
    r = await client.post(
        "/api/v1/expense-claims",
        json={
            "payer_kind": "owner",
            "payer_name": "Brent",
            "lines": [
                {
                    "description": "Coffee",
                    "expense_account_id": str(bogus_account_id),
                    "amount": "12.50",
                }
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert "Expense account" in detail
    assert str(bogus_account_id) in detail

    # No claim row should have been created.
    count = (
        await db_session.execute(select(func.count()).select_from(ExpenseClaim))
    ).scalar_one()
    assert count == 0
