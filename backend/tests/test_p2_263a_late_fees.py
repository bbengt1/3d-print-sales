"""#263 P2: late payment fee invoice generation."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.setting import Setting
from app.services.late_fee_service import run_late_fees_due


async def _customer(db_session, **overrides) -> Customer:
    c = Customer(name="Late Cust", email="l@x.x", **overrides)
    db_session.add(c)
    await db_session.flush()
    return c


async def _overdue_invoice(
    db_session, customer: Customer, *, due_offset_days: int = -45, balance: Decimal = Decimal("100")
) -> Invoice:
    today = datetime.date.today()
    inv = Invoice(
        invoice_number=f"INV-LATE-{customer.id.hex[:6]}",
        customer_id=customer.id,
        customer_name=customer.name,
        issue_date=today + datetime.timedelta(days=due_offset_days - 30),
        due_date=today + datetime.timedelta(days=due_offset_days),
        subtotal=balance,
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=balance,
        amount_paid=Decimal("0"),
        balance_due=balance,
        status="sent",
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(InvoiceLine(invoice_id=inv.id, description="X", quantity=1, unit_price=balance, line_total=balance))
    return inv


@pytest.mark.asyncio
async def test_late_fee_uses_customer_override(db_session):
    c = await _customer(
        db_session,
        late_payment_fee_rate_pct=Decimal("2.0"),
        late_payment_fee_grace_days=5,
    )
    inv = await _overdue_invoice(db_session, c, balance=Decimal("100"))
    await db_session.commit()
    summary = await run_late_fees_due(db_session)
    assert summary["generated_count"] == 1
    fee = (
        await db_session.execute(
            select(Invoice).where(Invoice.notes.like(f"%[late-fee-source:{inv.id}]%"))
        )
    ).scalar_one()
    # 100 * 2.0% = 2.00
    assert Decimal(fee.total_due) == Decimal("2.00")
    assert fee.status == "draft"


@pytest.mark.asyncio
async def test_late_fee_uses_global_setting_fallback(db_session):
    db_session.add(Setting(key="late_payment_fee_rate_pct", value="1.5", notes=""))
    db_session.add(Setting(key="late_payment_fee_grace_days", value="0", notes=""))
    c = await _customer(db_session)
    inv = await _overdue_invoice(db_session, c, balance=Decimal("200"))
    await db_session.commit()
    summary = await run_late_fees_due(db_session)
    assert summary["generated_count"] == 1
    fee = (
        await db_session.execute(
            select(Invoice).where(Invoice.notes.like(f"%[late-fee-source:{inv.id}]%"))
        )
    ).scalar_one()
    assert Decimal(fee.total_due) == Decimal("3.00")  # 200 × 1.5%


@pytest.mark.asyncio
async def test_late_fee_no_rate_skips(db_session):
    c = await _customer(db_session)  # no per-customer override and no global setting
    await _overdue_invoice(db_session, c)
    await db_session.commit()
    summary = await run_late_fees_due(db_session)
    assert summary["generated_count"] == 0
    assert summary["skipped"] >= 1


@pytest.mark.asyncio
async def test_late_fee_grace_period_blocks(db_session):
    c = await _customer(
        db_session,
        late_payment_fee_rate_pct=Decimal("2.0"),
        late_payment_fee_grace_days=60,
    )
    # Only 30 days past due, grace is 60 → no fee
    await _overdue_invoice(db_session, c, due_offset_days=-30, balance=Decimal("100"))
    await db_session.commit()
    summary = await run_late_fees_due(db_session)
    assert summary["generated_count"] == 0


@pytest.mark.asyncio
async def test_late_fee_idempotent_within_a_day(db_session):
    c = await _customer(
        db_session,
        late_payment_fee_rate_pct=Decimal("1.0"),
        late_payment_fee_grace_days=0,
    )
    inv = await _overdue_invoice(db_session, c, balance=Decimal("100"))
    await db_session.commit()
    s1 = await run_late_fees_due(db_session)
    await db_session.commit()
    s2 = await run_late_fees_due(db_session)
    assert s1["generated_count"] == 1
    assert s2["generated_count"] == 0
    fee_count = (
        await db_session.execute(
            select(Invoice).where(Invoice.notes.like(f"%[late-fee-source:{inv.id}]%"))
        )
    ).scalars().all()
    assert len(fee_count) == 1
