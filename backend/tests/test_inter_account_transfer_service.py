from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_line import JournalLine
from app.services.bank_reconciliation_service import (
    finalize_reconciliation,
    include_line,
    start_reconciliation,
)
from app.services.inter_account_transfer_service import (
    InterAccountTransferError,
    create_inter_account_transfer,
    delete_inter_account_transfer,
)


async def _bank(db_session, code, name):
    a = Account(
        code=code,
        name=name,
        account_type="asset",
        normal_balance="debit",
        is_bank_account=True,
        bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_happy_path_same_dates(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("500"),
        paid_on=datetime.date(2026, 5, 1),
    )
    assert t.transfer_number.startswith("T-")
    assert t.received_on == t.paid_on


@pytest.mark.asyncio
async def test_per_line_dates_differ(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("250"),
        paid_on=datetime.date(2026, 5, 1),
        received_on=datetime.date(2026, 5, 3),
    )
    lines = (await db_session.execute(select(JournalLine).order_by(JournalLine.line_number))).scalars().all()
    assert len(lines) == 2
    assert lines[0].posted_on == datetime.date(2026, 5, 1)
    assert lines[1].posted_on == datetime.date(2026, 5, 3)
    assert lines[0].entry_type == "credit"
    assert lines[1].entry_type == "debit"


@pytest.mark.asyncio
async def test_same_account_rejected(db_session):
    src = await _bank(db_session, "1010", "Operating")
    with pytest.raises(InterAccountTransferError):
        await create_inter_account_transfer(
            db_session,
            from_account_id=src.id,
            to_account_id=src.id,
            amount=Decimal("100"),
            paid_on=datetime.date(2026, 5, 1),
        )


@pytest.mark.asyncio
async def test_non_bank_account_rejected(db_session):
    src = await _bank(db_session, "1010", "Operating")
    not_bank = Account(code="9999", name="Not bank", account_type="asset", normal_balance="debit", is_bank_account=False)
    db_session.add(not_bank)
    await db_session.flush()
    with pytest.raises(InterAccountTransferError):
        await create_inter_account_transfer(
            db_session,
            from_account_id=src.id,
            to_account_id=not_bank.id,
            amount=Decimal("100"),
            paid_on=datetime.date(2026, 5, 1),
        )


@pytest.mark.asyncio
async def test_zero_amount_rejected(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    with pytest.raises(InterAccountTransferError):
        await create_inter_account_transfer(
            db_session,
            from_account_id=src.id,
            to_account_id=dst.id,
            amount=Decimal("0"),
            paid_on=datetime.date(2026, 5, 1),
        )


@pytest.mark.asyncio
async def test_delete_unreconciled(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("100"),
        paid_on=datetime.date(2026, 5, 1),
    )
    await delete_inter_account_transfer(db_session, t.id)


@pytest.mark.asyncio
async def test_delete_blocked_when_leg_reconciled(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("100"),
        paid_on=datetime.date(2026, 5, 1),
    )
    # Reconcile the from-side leg
    lines = (await db_session.execute(select(JournalLine).where(JournalLine.account_id == src.id))).scalars().all()
    line = lines[0]

    recon = await start_reconciliation(
        db_session,
        account_id=src.id,
        statement_end_date=datetime.date(2026, 5, 31),
        statement_ending_balance=Decimal("-100"),
    )
    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=line.id)
    await finalize_reconciliation(db_session, reconciliation_id=recon.id, finalized_by_user_id=None)

    with pytest.raises(InterAccountTransferError):
        await delete_inter_account_transfer(db_session, t.id)
