"""#333 Codex P1: API handler must map JournalLineLockedError -> client error.

`POST /accounting/journal-entries/{entry_id}/reverse` raises
`JournalLineLockedError` when any source line has `cleared_status="reconciled"`.
Previously the handler only caught `AccountingValidationError`, so this
condition surfaced as an unhandled HTTP 500. It must surface as a 4xx (409
Conflict — the operator needs to reopen the bank reconciliation first).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.accounting_service import (
    ensure_accounting_period,
    seed_chart_of_accounts,
)
from app.services.bank_reconciliation_service import CLEARED_STATUS_RECONCILED


@pytest.mark.asyncio
async def test_reverse_returns_409_when_any_source_line_is_reconciled(
    client, auth_headers, db_session: AsyncSession
):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-04",
        name="April 2026",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
    )

    accounts = (await client.get("/api/v1/accounting/accounts", headers=auth_headers)).json()
    cash = next(a for a in accounts if a["code"] == "1000")
    sales = next(a for a in accounts if a["code"] == "4000")

    create_payload = {
        "entry_date": "2026-04-15",
        "accounting_period_id": str(period.id),
        "source_type": "sale",
        "source_id": "S-2026-0333",
        "lines": [
            {"account_id": cash["id"], "entry_type": "debit", "amount": "42.00"},
            {"account_id": sales["id"], "entry_type": "credit", "amount": "42.00"},
        ],
    }
    create_resp = await client.post(
        "/api/v1/accounting/journal-entries", headers=auth_headers, json=create_payload
    )
    assert create_resp.status_code == 201, create_resp.text
    entry = create_resp.json()
    entry_id = uuid.UUID(entry["id"])

    # Mark the cash leg as reconciled at the model level — this is the state
    # `finalize_reconciliation` would persist after a successful bank recon.
    cash_account_id = uuid.UUID(cash["id"])
    cash_line = (
        await db_session.execute(
            select(JournalLine).where(
                JournalLine.journal_entry_id == entry_id,
                JournalLine.account_id == cash_account_id,
            )
        )
    ).scalar_one()
    cash_line.cleared_status = CLEARED_STATUS_RECONCILED
    await db_session.commit()

    # Attempt reversal — must be a client error, not a 500.
    reverse_resp = await client.post(
        f"/api/v1/accounting/journal-entries/{entry['id']}/reverse",
        headers=auth_headers,
        json={"reversal_date": "2026-04-20", "memo": "Should be blocked"},
    )
    assert 400 <= reverse_resp.status_code < 500, reverse_resp.text
    assert reverse_resp.status_code == 409, reverse_resp.text
    detail = reverse_resp.json()["detail"]
    assert "reconciled" in detail.lower()

    # Original JE must remain un-reversed: no reversal_of_id pointing at it.
    existing = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.reversal_of_id == entry_id)
        )
    ).scalar_one_or_none()
    assert existing is None
