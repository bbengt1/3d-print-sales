from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.report_service import (
    generate_receipts_payments_summary_report,
    generate_trial_balance_report,
)


async def _post_je(db_session, *, date, lines):
    """Helper. lines = [(account_code, entry_type, amount), ...]"""
    accts = {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}
    je = JournalEntry(
        entry_number=f"JE-T-{date.isoformat()}-{len(lines)}",
        entry_date=date,
        status="posted",
    )
    db_session.add(je)
    await db_session.flush()
    for i, (code, etype, amount) in enumerate(lines, start=1):
        db_session.add(
            JournalLine(
                journal_entry_id=je.id,
                account_id=accts[code].id,
                line_number=i,
                entry_type=etype,
                amount=Decimal(amount),
            )
        )
    await db_session.flush()


async def _flag_cash_as_bank(db_session):
    """Promote the seeded 1000 (Cash) account to ``is_bank_account=True``
    so the receipts/payments summary (cash-only by design after the
    PR #292 P1 fix) can pick up cash postings."""
    accts = {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}
    accts["1000"].is_bank_account = True
    await db_session.flush()


@pytest.mark.asyncio
async def test_trial_balance_empty(db_session):
    rep = await generate_trial_balance_report(db_session, datetime.date(2026, 12, 31))
    assert rep["rows"] == []
    assert rep["total_debit"] == Decimal("0")
    assert rep["total_credit"] == Decimal("0")
    assert rep["is_balanced"] is True


@pytest.mark.asyncio
async def test_trial_balance_balanced_after_postings(db_session):
    # Post: Dr Cash 100 / Cr Sales 100
    await _post_je(db_session, date=datetime.date(2026, 5, 1), lines=[
        ("1000", "debit", "100"),
        ("4000", "credit", "100"),
    ])
    rep = await generate_trial_balance_report(db_session, datetime.date(2026, 12, 31))
    assert rep["is_balanced"] is True
    assert rep["total_debit"] == Decimal("100")
    assert rep["total_credit"] == Decimal("100")
    codes = {r["account_code"] for r in rep["rows"]}
    assert "1000" in codes
    assert "4000" in codes


@pytest.mark.asyncio
async def test_trial_balance_respects_as_of_date(db_session):
    await _post_je(db_session, date=datetime.date(2026, 1, 1), lines=[
        ("1000", "debit", "50"),
        ("4000", "credit", "50"),
    ])
    await _post_je(db_session, date=datetime.date(2027, 1, 1), lines=[
        ("1000", "debit", "200"),
        ("4000", "credit", "200"),
    ])
    rep = await generate_trial_balance_report(db_session, datetime.date(2026, 12, 31))
    cash_row = next(r for r in rep["rows"] if r["account_code"] == "1000")
    assert cash_row["debit"] == Decimal("50")


@pytest.mark.asyncio
async def test_trial_balance_signs_negative_balances_correctly(db_session):
    # Post a contra-balance scenario: Cr Cash 30 / Dr Sales 30 → cash goes
    # negative on its natural side, so it should land in Credit column.
    # (Pretend Cash is overdrawn for the sake of the test.)
    await _post_je(db_session, date=datetime.date(2026, 5, 1), lines=[
        ("1000", "credit", "30"),
        ("4000", "debit", "30"),
    ])
    rep = await generate_trial_balance_report(db_session, datetime.date(2026, 12, 31))
    cash_row = next(r for r in rep["rows"] if r["account_code"] == "1000")
    assert cash_row["debit"] == Decimal("0")
    assert cash_row["credit"] == Decimal("30")


@pytest.mark.asyncio
async def test_receipts_payments_summary_empty(db_session):
    rep = await generate_receipts_payments_summary_report(db_session, None, None)
    assert rep["rows"] == []
    assert rep["total_inflows"] == Decimal("0")
    assert rep["total_outflows"] == Decimal("0")


@pytest.mark.asyncio
async def test_receipts_payments_summary_groups_by_account(db_session):
    await _flag_cash_as_bank(db_session)
    await _post_je(db_session, date=datetime.date(2026, 5, 1), lines=[
        ("1000", "debit", "500"),
        ("4000", "credit", "500"),
    ])
    await _post_je(db_session, date=datetime.date(2026, 5, 5), lines=[
        ("1000", "credit", "100"),
        ("6500", "debit", "100"),
    ])
    rep = await generate_receipts_payments_summary_report(
        db_session, datetime.date(2026, 5, 1), datetime.date(2026, 5, 31)
    )
    cash = next(r for r in rep["rows"] if r["account_code"] == "1000")
    assert cash["inflows"] == Decimal("500")
    assert cash["outflows"] == Decimal("100")
    assert cash["net"] == Decimal("400")
    assert cash["transaction_count"] == 2


@pytest.mark.asyncio
async def test_receipts_payments_summary_period_bounds(db_session):
    await _flag_cash_as_bank(db_session)
    await _post_je(db_session, date=datetime.date(2026, 1, 1), lines=[
        ("1000", "debit", "1000"),
        ("4000", "credit", "1000"),
    ])
    await _post_je(db_session, date=datetime.date(2026, 6, 1), lines=[
        ("1000", "debit", "200"),
        ("4000", "credit", "200"),
    ])
    rep = await generate_receipts_payments_summary_report(
        db_session, datetime.date(2026, 5, 1), datetime.date(2026, 12, 31)
    )
    cash = next(r for r in rep["rows"] if r["account_code"] == "1000")
    assert cash["inflows"] == Decimal("200")
    assert cash["transaction_count"] == 1
