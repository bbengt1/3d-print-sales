"""Regression test for #282 P1 (Codex review).

`PATCH /accounting/recurring-journal-entries/{rje_id}` previously dumped the
request body with `model_dump(exclude_unset=True)` and wrote the resulting
`lines_template` straight into the JSON column. Nested fields stayed as Python
objects (`UUID` for `account_id`, `Decimal` for `amount`), so SQLAlchemy's JSON
serializer would 500 at commit time instead of applying the update. The fix
mirrors the create handler by dumping each template line with `mode="json"`
before persisting.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.recurring_journal_entry import RecurringJournalEntry


@pytest.mark.asyncio
async def test_patch_rje_lines_template_serializes_uuid_and_decimal(
    client, auth_headers, db_session: AsyncSession
):
    accts = {
        a.code: a
        for a in (await db_session.execute(select(Account))).scalars().all()
    }
    software = accts["6100"]
    ap = accts["2000"]
    cash = accts["1000"]

    # Create an RJE via the service-style API (create handler already JSON-safe).
    create_resp = await client.post(
        "/api/v1/accounting/recurring-journal-entries",
        headers=auth_headers,
        json={
            "name": "Monthly accrual",
            "cadence": "monthly",
            "interval_count": 1,
            "start_on": date(2026, 1, 31).isoformat(),
            "memo": "Initial",
            "lines_template": [
                {
                    "account_id": str(software.id),
                    "entry_type": "debit",
                    "amount": "100.00",
                    "description": "Software",
                },
                {
                    "account_id": str(ap.id),
                    "entry_type": "credit",
                    "amount": "100.00",
                    "description": "AP",
                },
            ],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    rje_id = create_resp.json()["id"]

    # PATCH with a fresh template — exercises the previously-broken path where
    # nested UUID/Decimal would reach the JSON column unconverted.
    new_amount = Decimal("250.50")
    patch_resp = await client.patch(
        f"/api/v1/accounting/recurring-journal-entries/{rje_id}",
        headers=auth_headers,
        json={
            "memo": "Updated",
            "lines_template": [
                {
                    "account_id": str(cash.id),
                    "entry_type": "debit",
                    "amount": str(new_amount),
                    "description": "Cash debit",
                },
                {
                    "account_id": str(ap.id),
                    "entry_type": "credit",
                    "amount": str(new_amount),
                    "description": "AP credit",
                },
            ],
        },
    )
    # Before the fix this returned 500 because the JSON serializer choked on
    # the UUID/Decimal Python objects sitting inside `lines_template`.
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["memo"] == "Updated"
    assert len(body["lines_template"]) == 2
    assert body["lines_template"][0]["account_id"] == str(cash.id)
    assert Decimal(body["lines_template"][0]["amount"]) == new_amount

    # Re-fetch via list to confirm the row was actually persisted.
    list_resp = await client.get(
        "/api/v1/accounting/recurring-journal-entries",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    rows = [r for r in list_resp.json() if r["id"] == rje_id]
    assert rows, "patched RJE missing from list"
    persisted = rows[0]
    assert persisted["memo"] == "Updated"
    assert persisted["lines_template"][0]["account_id"] == str(cash.id)
    assert persisted["lines_template"][1]["account_id"] == str(ap.id)
    assert Decimal(persisted["lines_template"][0]["amount"]) == new_amount

    # And confirm the DB row stores JSON-safe primitives (no Python objects).
    refreshed = (
        await db_session.execute(
            select(RecurringJournalEntry).where(
                RecurringJournalEntry.id == uuid.UUID(rje_id)
            )
        )
    ).scalar_one()
    for line in refreshed.lines_template:
        assert isinstance(line["account_id"], str)
        # Decimal becomes a JSON string in mode="json"; never a raw Decimal.
        assert not isinstance(line["amount"], Decimal)
