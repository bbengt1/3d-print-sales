"""#263 P2: customer-side withholding tax."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.withholding_profile import WithholdingProfile
from app.services.withholding_service import (
    WithholdingError,
    apply_payment_with_withholding,
)


async def _seed(db_session):
    rows = [
        ("1000", "Cash", "asset", "debit"),
        ("1100", "Accounts Receivable", "asset", "debit"),
        ("1500", "Withholding receivable", "asset", "debit"),
    ]
    for code, name, kind, side in rows:
        existing = (await db_session.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
        if existing is None:
            db_session.add(Account(code=code, name=name, account_type=kind, normal_balance=side))
    await db_session.flush()
    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    liab = (await db_session.execute(select(Account).where(Account.code == "1500"))).scalar_one()
    return cash, liab


async def _customer_with_profile(db_session, liab_id, rate=Decimal("10.0")) -> Customer:
    profile = WithholdingProfile(name="WH 10%", rate_pct=rate, liability_account_id=liab_id)
    db_session.add(profile)
    await db_session.flush()
    c = Customer(name="WH Cust", email="wh@x.x", withholding_profile_id=profile.id)
    db_session.add(c)
    await db_session.flush()
    return c


async def _invoice(db_session, c) -> Invoice:
    inv = Invoice(
        invoice_number=f"INV-WH-{c.id.hex[:6]}",
        customer_id=c.id,
        customer_name=c.name,
        issue_date=datetime.date(2026, 5, 1),
        due_date=datetime.date(2026, 5, 31),
        subtotal=Decimal("100"),
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("100"),
        amount_paid=Decimal("0"),
        balance_due=Decimal("100"),
        status="sent",
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        InvoiceLine(invoice_id=inv.id, description="X", quantity=1, unit_price=Decimal("100"), line_total=Decimal("100"))
    )
    return inv


@pytest.mark.asyncio
async def test_apply_payment_with_withholding_splits_je(db_session):
    cash, liab = await _seed(db_session)
    c = await _customer_with_profile(db_session, liab.id, rate=Decimal("10"))
    inv = await _invoice(db_session, c)
    await db_session.commit()

    res = await apply_payment_with_withholding(
        db_session,
        invoice_id=inv.id,
        gross_amount=Decimal("100"),
        cash_account_id=cash.id,
        paid_on=datetime.date(2026, 5, 15),
    )
    assert Decimal(res["withheld"]) == Decimal("10.00")
    assert Decimal(res["cash_received"]) == Decimal("90.00")

    # JE legs
    je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "invoice_payment_withholding")
        )
    ).scalar_one()
    lines = (
        await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == je.id))
    ).scalars().all()
    sides = {(l.account_id, l.entry_type): Decimal(l.amount) for l in lines}
    ar = (await db_session.execute(select(Account).where(Account.code == "1100"))).scalar_one()
    assert sides[(cash.id, "debit")] == Decimal("90.00")
    assert sides[(liab.id, "debit")] == Decimal("10.00")
    assert sides[(ar.id, "credit")] == Decimal("100")

    # Invoice cleared
    refreshed = (await db_session.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert Decimal(refreshed.balance_due) == Decimal("0")
    assert refreshed.status == "paid"


@pytest.mark.asyncio
async def test_apply_payment_without_profile_raises(db_session):
    cash, _ = await _seed(db_session)
    c = Customer(name="no profile", email="n@x.x")
    db_session.add(c)
    await db_session.flush()
    inv = await _invoice(db_session, c)
    await db_session.commit()
    with pytest.raises(WithholdingError, match="no withholding profile"):
        await apply_payment_with_withholding(
            db_session, invoice_id=inv.id, gross_amount=Decimal("100"),
            cash_account_id=cash.id,
        )


@pytest.mark.asyncio
async def test_apply_payment_partial_keeps_invoice_open(db_session):
    cash, liab = await _seed(db_session)
    c = await _customer_with_profile(db_session, liab.id, rate=Decimal("5"))
    inv = await _invoice(db_session, c)
    await db_session.commit()
    await apply_payment_with_withholding(
        db_session, invoice_id=inv.id, gross_amount=Decimal("60"),
        cash_account_id=cash.id,
    )
    refreshed = (await db_session.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert Decimal(refreshed.balance_due) == Decimal("40")
    assert refreshed.status == "partially_paid"
