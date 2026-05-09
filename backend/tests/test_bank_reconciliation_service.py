from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.bank_reconciliation import BankReconciliation
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.bank_reconciliation_service import (
    BankReconciliationError,
    JournalLineLockedError,
    assert_journal_line_editable,
    compute_account_balance,
    exclude_line,
    finalize_reconciliation,
    include_line,
    reopen_reconciliation,
    start_reconciliation,
)


# ---------- helpers ----------


async def _make_bank_account(db_session, code="1010", name="Operating Checking", kind="checking"):
    a = Account(
        code=code,
        name=name,
        account_type="asset",
        normal_balance="debit",
        is_active=True,
        is_bank_account=True,
        bank_account_kind=kind,
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


# ---------- tests ----------


@pytest.mark.asyncio
async def test_start_reconciliation_requires_bank_account(db_session):
    a = Account(
        code="9999",
        name="Not a bank",
        account_type="asset",
        normal_balance="debit",
        is_bank_account=False,
    )
    db_session.add(a)
    await db_session.flush()
    with pytest.raises(BankReconciliationError):
        await start_reconciliation(
            db_session,
            account_id=a.id,
            statement_end_date=datetime.date(2026, 1, 31),
            statement_ending_balance=Decimal("100"),
        )


@pytest.mark.asyncio
async def test_compute_balance_matches_signed_sum(db_session):
    a = await _make_bank_account(db_session)
    await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=500, n=1)
    await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 5), credit=200, n=2)
    bal = await compute_account_balance(db_session, a.id)
    assert bal == Decimal("300")


@pytest.mark.asyncio
async def test_finalize_blocks_when_balances_differ(db_session):
    a = await _make_bank_account(db_session)
    await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=100, n=1)
    recon = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("999"),  # mismatched on purpose
    )
    # No lines included → book balance == opening (0); 0 != 999 → finalize blocked
    with pytest.raises(BankReconciliationError):
        await finalize_reconciliation(db_session, reconciliation_id=recon.id, finalized_by_user_id=None)


@pytest.mark.asyncio
async def test_full_lifecycle_finalize_and_lock(db_session):
    a = await _make_bank_account(db_session)
    _, line1 = await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=500, n=1)
    _, line2 = await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 10), credit=200, n=2)

    recon = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("300"),
    )

    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=line1.id)
    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=line2.id)

    finalized = await finalize_reconciliation(
        db_session, reconciliation_id=recon.id, finalized_by_user_id=None
    )
    assert finalized.status == "finalized"
    assert finalized.finalized_at is not None

    refreshed_line = (await db_session.execute(select(JournalLine).where(JournalLine.id == line1.id))).scalar_one()
    assert refreshed_line.cleared_status == "reconciled"

    with pytest.raises(JournalLineLockedError):
        await assert_journal_line_editable(db_session, line1.id)


@pytest.mark.asyncio
async def test_exclude_line_flips_back_to_uncleared(db_session):
    a = await _make_bank_account(db_session)
    _, line = await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=100, n=1)
    recon = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("0"),
    )
    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=line.id)
    refreshed = (await db_session.execute(select(JournalLine).where(JournalLine.id == line.id))).scalar_one()
    assert refreshed.cleared_status == "cleared"

    await exclude_line(db_session, reconciliation_id=recon.id, journal_line_id=line.id)
    refreshed = (await db_session.execute(select(JournalLine).where(JournalLine.id == line.id))).scalar_one()
    assert refreshed.cleared_status == "uncleared"


@pytest.mark.asyncio
async def test_reopen_finalized_recon(db_session):
    a = await _make_bank_account(db_session)
    _, line = await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=100, n=1)
    recon = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("100"),
    )
    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=line.id)
    await finalize_reconciliation(db_session, reconciliation_id=recon.id, finalized_by_user_id=None)

    reopened = await reopen_reconciliation(db_session, reconciliation_id=recon.id)
    assert reopened.status == "in_progress"
    assert reopened.finalized_at is None

    refreshed = (await db_session.execute(select(JournalLine).where(JournalLine.id == line.id))).scalar_one()
    # After reopen the line goes back to cleared (still on the recon, ready for re-finalize)
    assert refreshed.cleared_status == "cleared"
    # Edit lock is released
    await assert_journal_line_editable(db_session, line.id)


@pytest.mark.asyncio
async def test_reopen_only_works_on_finalized_recons(db_session):
    a = await _make_bank_account(db_session)
    recon = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("0"),
    )
    with pytest.raises(BankReconciliationError):
        await reopen_reconciliation(db_session, reconciliation_id=recon.id)


@pytest.mark.asyncio
async def test_cannot_include_already_reconciled_line(db_session):
    a = await _make_bank_account(db_session)
    _, line = await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=50, n=1)

    r1 = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 1, 31),
        statement_ending_balance=Decimal("50"),
    )
    await include_line(db_session, reconciliation_id=r1.id, journal_line_id=line.id)
    await finalize_reconciliation(db_session, reconciliation_id=r1.id, finalized_by_user_id=None)

    r2 = await start_reconciliation(
        db_session,
        account_id=a.id,
        statement_end_date=datetime.date(2026, 2, 28),
        statement_ending_balance=Decimal("50"),
    )
    with pytest.raises(BankReconciliationError):
        await include_line(db_session, reconciliation_id=r2.id, journal_line_id=line.id)


@pytest.mark.asyncio
async def test_assert_editable_on_uncleared_line_is_noop(db_session):
    a = await _make_bank_account(db_session)
    _, line = await _post_je(db_session, a, entry_date=datetime.date(2026, 1, 1), debit=10, n=1)
    # Should not raise
    await assert_journal_line_editable(db_session, line.id)
