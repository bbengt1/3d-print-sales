"""Codex P1 review on PR #275: inter-account transfer legs must reconcile by
their own posted dates.

Before the fix, `list_eligible_lines` and `compute_account_balance` filtered
by `JournalEntry.entry_date` (set to `min(paid_on, received_on)`), so the
receiving leg of a delayed-receipt transfer became visible on the source
account's earlier statement date — letting it reconcile against the wrong
statement. The fix uses each line's `posted_on` (falling back to
`entry_date`) as the effective per-leg date.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_line import JournalLine
from app.services.bank_reconciliation_service import (
    compute_account_balance,
    list_eligible_lines,
)
from app.services.inter_account_transfer_service import (
    create_inter_account_transfer,
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
async def test_each_leg_dated_by_its_own_posted_on(db_session):
    """Source line carries paid_on; destination line carries received_on."""
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")

    paid_on = datetime.date(2026, 5, 1)
    received_on = datetime.date(2026, 5, 3)

    await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("500"),
        paid_on=paid_on,
        received_on=received_on,
    )

    src_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.account_id == src.id)
        )
    ).scalar_one()
    dst_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.account_id == dst.id)
        )
    ).scalar_one()

    assert src_line.posted_on == paid_on
    assert dst_line.posted_on == received_on


@pytest.mark.asyncio
async def test_destination_leg_not_eligible_before_received_on(db_session):
    """A May-1 statement on the destination account must NOT see a May-3
    receiving leg, even though the JE's entry_date is May 1.
    """
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")

    paid_on = datetime.date(2026, 5, 1)
    received_on = datetime.date(2026, 5, 3)

    await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("500"),
        paid_on=paid_on,
        received_on=received_on,
    )

    # On May 1 (the statement-end-date), the destination account should
    # have NO eligible lines: the receiving leg is dated May 3.
    eligible_dst_may1 = await list_eligible_lines(
        db_session,
        account_id=dst.id,
        statement_end_date=paid_on,
    )
    assert eligible_dst_may1 == []

    # On May 1, the source account *should* see its outgoing leg.
    eligible_src_may1 = await list_eligible_lines(
        db_session,
        account_id=src.id,
        statement_end_date=paid_on,
    )
    assert len(eligible_src_may1) == 1
    line, _entry = eligible_src_may1[0]
    assert line.account_id == src.id
    assert line.posted_on == paid_on

    # On May 3, the destination leg is now eligible.
    eligible_dst_may3 = await list_eligible_lines(
        db_session,
        account_id=dst.id,
        statement_end_date=received_on,
    )
    assert len(eligible_dst_may3) == 1
    line, _entry = eligible_dst_may3[0]
    assert line.account_id == dst.id
    assert line.posted_on == received_on


@pytest.mark.asyncio
async def test_through_date_balance_uses_per_leg_date(db_session):
    """Opening balance computed through_date=May-1 on the destination
    account must NOT include the May-3 receiving leg.
    """
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")

    paid_on = datetime.date(2026, 5, 1)
    received_on = datetime.date(2026, 5, 3)

    await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("500"),
        paid_on=paid_on,
        received_on=received_on,
    )

    # Through May 1: destination has zero (receipt is in the future).
    bal_dst_may1 = await compute_account_balance(
        db_session, dst.id, through_date=paid_on
    )
    assert bal_dst_may1 == Decimal("0")

    # Through May 3: destination shows +500.
    bal_dst_may3 = await compute_account_balance(
        db_session, dst.id, through_date=received_on
    )
    assert bal_dst_may3 == Decimal("500")

    # Through May 1: source already shows -500 (paid out on May 1).
    bal_src_may1 = await compute_account_balance(
        db_session, src.id, through_date=paid_on
    )
    assert bal_src_may1 == Decimal("-500")
