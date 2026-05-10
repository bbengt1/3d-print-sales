"""#314 P2: period-close date enforcement + JE edit-lock coverage."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_line import JournalLine
from app.schemas.accounting import JournalEntryReverse
from app.services.accounting_service import (
    AccountingValidationError,
    assert_financial_date_editable,
    create_journal_entry,
    get_period_close_date,
    reverse_journal_entry,
    set_period_close_date,
)
from app.services.bank_reconciliation_service import (
    JournalLineLockedError,
    finalize_reconciliation,
    include_line,
    start_reconciliation,
)
from app.services.inter_account_transfer_service import (
    create_inter_account_transfer,
)


async def _bank(db_session, code, name) -> Account:
    a = Account(
        code=code, name=name, account_type="asset", normal_balance="debit",
        is_bank_account=True, bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_set_and_get_period_close_date(db_session):
    assert await get_period_close_date(db_session) is None
    await set_period_close_date(db_session, close_date=datetime.date(2026, 3, 31))
    await db_session.commit()
    assert await get_period_close_date(db_session) == datetime.date(2026, 3, 31)


@pytest.mark.asyncio
async def test_assert_financial_date_editable_refuses_on_or_before_close(db_session):
    await set_period_close_date(db_session, close_date=datetime.date(2026, 3, 31))
    await db_session.commit()
    # On the close date is refused
    with pytest.raises(AccountingValidationError):
        await assert_financial_date_editable(db_session, target_date=datetime.date(2026, 3, 31))
    # Before the close date is refused
    with pytest.raises(AccountingValidationError):
        await assert_financial_date_editable(db_session, target_date=datetime.date(2026, 3, 1))
    # After the close date is allowed
    await assert_financial_date_editable(db_session, target_date=datetime.date(2026, 4, 1))


@pytest.mark.asyncio
async def test_clearing_close_date_unblocks_mutations(db_session):
    await set_period_close_date(db_session, close_date=datetime.date(2026, 3, 31))
    await db_session.commit()
    with pytest.raises(AccountingValidationError):
        await assert_financial_date_editable(db_session, target_date=datetime.date(2026, 3, 1))
    await set_period_close_date(db_session, close_date=None)
    await db_session.commit()
    # No exception now
    await assert_financial_date_editable(db_session, target_date=datetime.date(2026, 3, 1))


@pytest.mark.asyncio
async def test_finalize_reconciliation_refused_when_stmt_end_in_closed_period(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    # Make some activity so book balance is well-defined
    await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("100"),
        paid_on=datetime.date(2026, 4, 1),
    )
    recon = await start_reconciliation(
        db_session,
        account_id=src.id,
        statement_end_date=datetime.date(2026, 3, 31),
        statement_ending_balance=Decimal("0"),
    )
    await set_period_close_date(db_session, close_date=datetime.date(2026, 3, 31))
    await db_session.commit()
    from app.services.bank_reconciliation_service import BankReconciliationError

    with pytest.raises(BankReconciliationError, match="closed-period"):
        await finalize_reconciliation(
            db_session, reconciliation_id=recon.id, finalized_by_user_id=None
        )


@pytest.mark.asyncio
async def test_reverse_journal_entry_blocked_by_reconciled_line(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("100"),
        paid_on=datetime.date(2026, 5, 1),
    )
    src_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.account_id == src.id).limit(1)
        )
    ).scalar_one()
    recon = await start_reconciliation(
        db_session,
        account_id=src.id,
        statement_end_date=datetime.date(2026, 5, 31),
        statement_ending_balance=Decimal("-100"),
    )
    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=src_line.id)
    await finalize_reconciliation(
        db_session, reconciliation_id=recon.id, finalized_by_user_id=None
    )

    with pytest.raises(JournalLineLockedError):
        await reverse_journal_entry(
            db_session,
            entry_id=t.journal_entry_id,
            payload=JournalEntryReverse(reversal_date=datetime.date(2026, 6, 1)),
        )


@pytest.mark.asyncio
async def test_reverse_journal_entry_blocked_by_closed_period(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("100"),
        paid_on=datetime.date(2026, 5, 1),
    )
    await set_period_close_date(db_session, close_date=datetime.date(2026, 5, 31))
    await db_session.commit()
    with pytest.raises(AccountingValidationError, match="closed period"):
        await reverse_journal_entry(
            db_session,
            entry_id=t.journal_entry_id,
            payload=JournalEntryReverse(reversal_date=datetime.date(2026, 5, 15)),
        )
