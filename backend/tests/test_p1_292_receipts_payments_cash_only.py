"""Regression: receipts/payments summary must scope to cash/bank accounts.

Codex P1 review on PR #292: ``generate_receipts_payments_summary_report``
joined Account against every posted journal line, so the report aggregated
the entire double-entry ledger rather than cash movement. In any balanced
period, that drives ``total_inflows`` and ``total_outflows`` to mirror
each other and emits non-cash accounts (revenue, COGS, AR/AP, etc.) as
bogus "receipts/payments" rows. Restrict to ``is_bank_account=True``.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.report_service import generate_receipts_payments_summary_report


async def _accounts(db_session):
    return {
        a.code: a
        for a in (await db_session.execute(select(Account))).scalars().all()
    }


async def _post_je(db_session, *, number, entry_date, debit, credit, amount):
    """Post a balanced journal entry with one debit and one credit line."""
    je = JournalEntry(
        entry_number=number, entry_date=entry_date, status="posted"
    )
    db_session.add(je)
    await db_session.flush()
    db_session.add(
        JournalLine(
            journal_entry_id=je.id,
            account_id=debit.id,
            line_number=1,
            entry_type="debit",
            amount=Decimal(amount),
        )
    )
    db_session.add(
        JournalLine(
            journal_entry_id=je.id,
            account_id=credit.id,
            line_number=2,
            entry_type="credit",
            amount=Decimal(amount),
        )
    )
    await db_session.flush()
    return je


@pytest.mark.asyncio
async def test_receipts_payments_summary_scopes_to_bank_accounts(db_session):
    accts = await _accounts(db_session)
    # Promote 1000 (Cash) to a bank account; the seeded chart leaves
    # is_bank_account=False by default.
    bank = accts["1000"]
    bank.is_bank_account = True
    await db_session.flush()

    revenue = accts["4000"]  # Product Sales
    expense = accts["6500"]  # Office & Supplies
    cogs = accts["5000"]  # Material COGS

    period_date = datetime.date(2026, 5, 1)

    # 1) Bank receives cash from revenue: debit Cash 300, credit Revenue 300.
    #    -> inflow on bank account (cash receipt).
    await _post_je(
        db_session,
        number="JE-CASH-IN",
        entry_date=period_date,
        debit=bank,
        credit=revenue,
        amount="300",
    )
    # 2) Bank pays expense: debit Expense 100, credit Cash 100.
    #    -> outflow on bank account (cash payment).
    await _post_je(
        db_session,
        number="JE-CASH-OUT",
        entry_date=period_date,
        debit=expense,
        credit=bank,
        amount="100",
    )
    # 3) Non-cash double-entry: debit COGS 50, credit Revenue 50.
    #    -> must NOT appear in receipts/payments. Crucially, this entry
    #    keeps the ledger balanced; if the report swept every posted line
    #    it would force inflows == outflows for the period.
    await _post_je(
        db_session,
        number="JE-NONCASH",
        entry_date=period_date,
        debit=cogs,
        credit=revenue,
        amount="50",
    )
    await db_session.commit()

    report = await generate_receipts_payments_summary_report(
        db_session, date_from=period_date, date_to=period_date
    )

    # Only the bank account should show up; revenue/expense/COGS are
    # excluded.
    codes = {row["account_code"] for row in report["rows"]}
    assert codes == {"1000"}, f"unexpected non-cash rows: {codes}"

    bank_row = next(r for r in report["rows"] if r["account_code"] == "1000")
    assert bank_row["is_bank_account"] is True
    assert bank_row["inflows"] == Decimal("300")
    assert bank_row["outflows"] == Decimal("100")
    assert bank_row["net"] == Decimal("200")
    # Two postings touched the bank account.
    assert bank_row["transaction_count"] == 2

    # Totals reflect cash movement only, and inflows must NOT equal
    # outflows (the bug forces them to mirror).
    assert report["total_inflows"] == Decimal("300")
    assert report["total_outflows"] == Decimal("100")
    assert report["total_inflows"] != report["total_outflows"]
    assert report["net_change"] == Decimal("200")


@pytest.mark.asyncio
async def test_receipts_payments_summary_empty_when_no_bank_accounts(
    db_session,
):
    """If no account is flagged as bank, the report is empty even when
    there is significant non-cash activity. This is the safe default and
    pins the cash-movement semantics."""
    accts = await _accounts(db_session)
    revenue = accts["4000"]
    cogs = accts["5000"]

    await _post_je(
        db_session,
        number="JE-NONCASH-ONLY",
        entry_date=datetime.date(2026, 5, 1),
        debit=cogs,
        credit=revenue,
        amount="999",
    )
    await db_session.commit()

    report = await generate_receipts_payments_summary_report(
        db_session, date_from=None, date_to=None
    )
    assert report["rows"] == []
    assert report["total_inflows"] == Decimal("0")
    assert report["total_outflows"] == Decimal("0")
    assert report["net_change"] == Decimal("0")
