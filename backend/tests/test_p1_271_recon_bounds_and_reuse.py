"""Regression tests for #271 P1 (Codex review on PR #271).

Two bugs in `include_line`:

1. The function never validated the journal line's `entry_date` against the
   reconciliation's `statement_end_date`, so a client could include a
   future-dated transaction in an older statement reconciliation.
2. The duplicate check only scoped to the current reconciliation, so a line
   could be linked into multiple active (in_progress) reconciliations
   simultaneously, double-counting the same transaction.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.bank_reconciliation_service import (
    BankReconciliationError,
    include_line,
    start_reconciliation,
)


async def _make_bank_account(db_session, code="1010"):
    a = Account(
        code=code,
        name="Operating Checking",
        account_type="asset",
        normal_balance="debit",
        is_active=True,
        is_bank_account=True,
        bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _post_je(db_session, account, *, entry_date, debit=None, credit=None, n=1):
    e = JournalEntry(
        entry_number=f"JE-{n}",
        entry_date=entry_date,
        status="posted",
    )
    db_session.add(e)
    await db_session.flush()
    line = JournalLine(
        journal_entry_id=e.id,
        account_id=account.id,
        line_number=1,
        entry_type="debit" if debit is not None else "credit",
        amount=Decimal(debit if debit is not None else credit),
    )
    db_session.add(line)
    await db_session.flush()
    return e, line


@pytest.mark.asyncio
async def test_include_line_rejects_entry_after_statement_end_date(db_session):
    """A journal line dated AFTER the statement_end_date must not be
    includable, even though `/toggle-line` accepts an arbitrary
    journal_line_id."""
    a = await _make_bank_account(db_session)
    # Reconciliation through Jan 31
    recon = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("0"),
    )
    # Journal line dated Feb 5 — outside the statement window
    _, future_line = await _post_je(
        db_session, a, entry_date=datetime.date(2026, 2, 5), debit=100, n=1
    )

    with pytest.raises(BankReconciliationError) as excinfo:
        await include_line(
            db_session,
            reconciliation_id=recon.id,
            journal_line_id=future_line.id,
        )
    assert "statement end date" in str(excinfo.value).lower() or "after" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_include_line_blocks_reuse_across_active_recons(db_session):
    """A journal line already linked to one in-progress reconciliation must
    not be includable into a second active reconciliation; otherwise the
    same transaction can be double-counted."""
    a = await _make_bank_account(db_session, code="1011")
    _, line = await _post_je(
        db_session, a, entry_date=datetime.date(2026, 1, 10), debit=100, n=1
    )

    r1 = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("100"),
    )
    await include_line(db_session, reconciliation_id=r1.id, journal_line_id=line.id)

    # Operator opens a second, overlapping in-progress reconciliation that
    # also covers this date range.
    r2 = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 2, 28),
        statement_ending_balance=Decimal("100"),
    )

    with pytest.raises(BankReconciliationError) as excinfo:
        await include_line(
            db_session,
            reconciliation_id=r2.id,
            journal_line_id=line.id,
        )
    assert "another" in str(excinfo.value).lower() or "active" in str(excinfo.value).lower()
