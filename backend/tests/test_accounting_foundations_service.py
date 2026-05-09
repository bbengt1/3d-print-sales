from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.recurring_journal_entry import RecurringJournalEntry
from app.services.accounting_foundations_service import (
    AccountingFoundationsError,
    post_starting_balances,
    run_due_jes,
    run_one_je,
    skip_next_je,
    suspense_report,
)


async def _accounts(db_session):
    return {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}


async def _make_rje(db_session, accts, *, start=datetime.date(2026, 1, 31)):
    rje = RecurringJournalEntry(
        name="Monthly accrual",
        cadence="monthly",
        interval_count=1,
        start_on=start,
        next_run_on=start,
        memo="Monthly software accrual",
        lines_template=[
            {"account_id": str(accts["6100"].id), "entry_type": "debit", "amount": "100", "description": "Software"},
            {"account_id": str(accts["2000"].id), "entry_type": "credit", "amount": "100", "description": "AP"},
        ],
    )
    db_session.add(rje)
    await db_session.flush()
    return rje


@pytest.mark.asyncio
async def test_run_one_generates_je_and_advances(db_session):
    accts = await _accounts(db_session)
    rje = await _make_rje(db_session, accts)
    run = await run_one_je(db_session, recurring_id=rje.id)
    assert run.status == "succeeded"
    assert run.generated_journal_entry_id is not None
    refreshed = (await db_session.execute(select(RecurringJournalEntry).where(RecurringJournalEntry.id == rje.id))).scalar_one()
    assert refreshed.next_run_on == datetime.date(2026, 2, 28)


@pytest.mark.asyncio
async def test_run_one_paused_rejected(db_session):
    accts = await _accounts(db_session)
    rje = await _make_rje(db_session, accts)
    rje.is_active = False
    await db_session.flush()
    with pytest.raises(AccountingFoundationsError):
        await run_one_je(db_session, recurring_id=rje.id)


@pytest.mark.asyncio
async def test_failure_does_not_advance(db_session):
    accts = await _accounts(db_session)
    rje = await _make_rje(db_session, accts)
    rje.lines_template = [
        {"account_id": str(accts["6100"].id), "entry_type": "debit", "amount": "100"},
    ]  # one line — invalid (need ≥ 2)
    await db_session.flush()
    run = await run_one_je(db_session, recurring_id=rje.id)
    assert run.status == "failed"
    refreshed = (await db_session.execute(select(RecurringJournalEntry).where(RecurringJournalEntry.id == rje.id))).scalar_one()
    assert refreshed.next_run_on == datetime.date(2026, 1, 31)


@pytest.mark.asyncio
async def test_skip_next_advances_without_je(db_session):
    accts = await _accounts(db_session)
    rje = await _make_rje(db_session, accts)
    run = await skip_next_je(db_session, rje.id)
    assert run.status == "skipped"
    assert run.generated_journal_entry_id is None


@pytest.mark.asyncio
async def test_run_due_jes(db_session):
    accts = await _accounts(db_session)
    await _make_rje(db_session, accts, start=datetime.date(2026, 1, 31))
    summary = await run_due_jes(db_session, today=datetime.date(2026, 2, 15))
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0


@pytest.mark.asyncio
async def test_suspense_report_empty(db_session):
    report = await suspense_report(db_session)
    assert report["configured"] is True
    assert Decimal(report["balance"]) == Decimal("0.00")
    assert report["lines"] == []


@pytest.mark.asyncio
async def test_suspense_report_after_posting(db_session):
    accts = await _accounts(db_session)
    suspense = accts["1900"]
    je = JournalEntry(entry_number="JE-1", entry_date=datetime.date(2026, 5, 1), status="posted")
    db_session.add(je)
    await db_session.flush()
    db_session.add(JournalLine(
        journal_entry_id=je.id, account_id=suspense.id, line_number=1,
        entry_type="debit", amount=Decimal("50"),
    ))
    db_session.add(JournalLine(
        journal_entry_id=je.id, account_id=accts["1000"].id, line_number=2,
        entry_type="credit", amount=Decimal("50"),
    ))
    await db_session.flush()
    report = await suspense_report(db_session)
    assert Decimal(report["balance"]) == Decimal("50.00")
    assert len(report["lines"]) == 1


@pytest.mark.asyncio
async def test_starting_balances_posts_je(db_session):
    accts = await _accounts(db_session)
    je = await post_starting_balances(
        db_session,
        as_of=datetime.date(2026, 1, 1),
        balances=[
            {"account_id": accts["1000"].id, "amount": Decimal("5000")},  # cash debit
            {"account_id": accts["1200"].id, "amount": Decimal("2000")},  # raw materials debit
        ],
        force=True,  # bypass activity guard for test
    )
    assert je.entry_number is not None
    # JE balanced
    lines = (await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == je.id))).scalars().all()
    debits = sum((Decimal(l.amount) for l in lines if l.entry_type == "debit"), Decimal("0"))
    credits = sum((Decimal(l.amount) for l in lines if l.entry_type == "credit"), Decimal("0"))
    assert debits == credits


@pytest.mark.asyncio
async def test_starting_balances_empty_rejected(db_session):
    with pytest.raises(AccountingFoundationsError):
        await post_starting_balances(
            db_session,
            as_of=datetime.date(2026, 1, 1),
            balances=[],
            force=True,
        )
