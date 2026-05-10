"""#321 P2: cash refund of credit notes."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.credit_note import CreditNote, CreditNoteLine
from app.models.customer import Customer
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.note_service import (
    NoteError,
    create_credit_note,
    issue_credit_note,
    refund_credit_note_in_cash,
)


async def _seed_min(db_session):
    rows = [
        ("1000", "Cash", "asset", "debit"),
        ("1100", "Accounts Receivable", "asset", "debit"),
        ("4000", "Sales Revenue", "revenue", "credit"),
        ("4800", "Sales Returns", "revenue", "debit"),
    ]
    for code, name, kind, side in rows:
        existing = (await db_session.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
        if existing is None:
            db_session.add(Account(code=code, name=name, account_type=kind, normal_balance=side))
    await db_session.flush()
    rev = (await db_session.execute(select(Account).where(Account.code == "4000"))).scalar_one()
    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    return rev, cash


async def _customer(db_session) -> Customer:
    c = Customer(name="Refundee", email="r@x.x")
    db_session.add(c)
    await db_session.flush()
    return c


@pytest.mark.asyncio
async def test_refund_in_cash_posts_je(db_session):
    rev, cash = await _seed_min(db_session)
    c = await _customer(db_session)
    note = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 4, 15),
        lines=[
            {"description": "Returned widget", "quantity": "1", "unit_price": "50",
             "account_id": rev.id},
        ],
    )
    await issue_credit_note(db_session, note.id)
    await refund_credit_note_in_cash(
        db_session,
        note_id=note.id,
        cash_account_id=cash.id,
        paid_on=datetime.date(2026, 4, 20),
    )

    sales_returns = (await db_session.execute(select(Account).where(Account.code == "4800"))).scalar_one()
    refund_je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "credit_note_refund")
        )
    ).scalar_one()
    lines = (
        await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == refund_je.id))
    ).scalars().all()
    sides = {(l.account_id, l.entry_type): Decimal(l.amount) for l in lines}
    assert sides[(sales_returns.id, "debit")] == Decimal("50")
    assert sides[(cash.id, "credit")] == Decimal("50")

    refreshed = (
        await db_session.execute(select(CreditNote).where(CreditNote.id == note.id))
    ).scalar_one()
    assert refreshed.status == "applied"
    assert Decimal(refreshed.applied_amount) == Decimal("50")


@pytest.mark.asyncio
async def test_refund_in_cash_after_partial_application(db_session):
    rev, cash = await _seed_min(db_session)
    c = await _customer(db_session)
    note = CreditNote(
        credit_note_number="CN-1",
        customer_id=c.id,
        issued_on=datetime.date(2026, 4, 15),
        total_amount=Decimal("80"),
        applied_amount=Decimal("30"),
        status="partially_applied",
    )
    db_session.add(note)
    await db_session.flush()
    db_session.add(CreditNoteLine(credit_note_id=note.id, description="X", quantity=Decimal("1"), unit_price=Decimal("80"), line_total=Decimal("80"), account_id=rev.id))
    await db_session.flush()

    await refund_credit_note_in_cash(
        db_session, note_id=note.id, cash_account_id=cash.id,
        paid_on=datetime.date(2026, 4, 25),
    )

    refund_je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "credit_note_refund")
        )
    ).scalar_one()
    lines = (
        await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == refund_je.id))
    ).scalars().all()
    cash_credit = next(l for l in lines if l.account_id == cash.id and l.entry_type == "credit")
    assert Decimal(cash_credit.amount) == Decimal("50")


@pytest.mark.asyncio
async def test_refund_with_no_remaining_credit_raises(db_session):
    rev, cash = await _seed_min(db_session)
    c = await _customer(db_session)
    note = CreditNote(
        credit_note_number="CN-2",
        customer_id=c.id,
        issued_on=datetime.date(2026, 4, 15),
        total_amount=Decimal("10"),
        applied_amount=Decimal("10"),
        status="applied",
    )
    db_session.add(note)
    await db_session.flush()
    with pytest.raises(NoteError):
        await refund_credit_note_in_cash(
            db_session, note_id=note.id, cash_account_id=cash.id,
        )
