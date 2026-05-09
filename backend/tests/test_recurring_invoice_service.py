from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.recurring_invoice import RecurringInvoice, RecurringInvoiceRun
from app.services.recurring_invoice_service import (
    RecurringInvoiceError,
    advance_date,
    run_due,
    run_one,
    skip_next,
)


async def _customer(db_session, name="Acme") -> Customer:
    c = Customer(name=name, email="customer@example.com")
    db_session.add(c)
    await db_session.flush()
    return c


async def _rule(
    db_session,
    customer_id,
    *,
    cadence="monthly",
    interval=1,
    start=datetime.date(2026, 1, 15),
    end=None,
):
    r = RecurringInvoice(
        name="Monthly retainer",
        customer_id=customer_id,
        cadence=cadence,
        interval_count=interval,
        start_on=start,
        next_run_on=start,
        end_on=end,
        line_items_template=[
            {"description": "Retainer", "quantity": 1, "unit_price": "100.00"},
        ],
        due_in_days=30,
    )
    db_session.add(r)
    await db_session.flush()
    return r


def test_advance_date_monthly():
    assert advance_date(datetime.date(2026, 1, 15), "monthly", 1) == datetime.date(2026, 2, 15)
    # End-of-month wrap: Jan 31 → Feb 28 (non-leap) but 2028 is leap
    assert advance_date(datetime.date(2026, 1, 31), "monthly", 1) == datetime.date(2026, 2, 28)
    assert advance_date(datetime.date(2026, 1, 31), "monthly", 13) == datetime.date(2027, 2, 28)


def test_advance_date_weekly():
    assert advance_date(datetime.date(2026, 1, 1), "weekly", 1) == datetime.date(2026, 1, 8)
    assert advance_date(datetime.date(2026, 1, 1), "weekly", 4) == datetime.date(2026, 1, 29)


def test_advance_date_daily():
    assert advance_date(datetime.date(2026, 1, 1), "daily", 7) == datetime.date(2026, 1, 8)


def test_advance_date_yearly_leap_handling():
    # Feb 29 (in 2024 leap year) → Feb 28 next year
    assert advance_date(datetime.date(2024, 2, 29), "yearly", 1) == datetime.date(2025, 2, 28)
    # Feb 29 → Feb 29 next leap year
    assert advance_date(datetime.date(2024, 2, 29), "yearly", 4) == datetime.date(2028, 2, 29)


def test_advance_date_unknown_cadence():
    with pytest.raises(RecurringInvoiceError):
        advance_date(datetime.date(2026, 1, 1), "biweekly", 1)


@pytest.mark.asyncio
async def test_run_one_generates_invoice_and_advances(db_session):
    c = await _customer(db_session)
    r = await _rule(db_session, c.id)

    run = await run_one(db_session, recurring_id=r.id)
    assert run.status == "succeeded"
    assert run.generated_invoice_id is not None

    refreshed = (await db_session.execute(select(RecurringInvoice).where(RecurringInvoice.id == r.id))).scalar_one()
    assert refreshed.last_run_on == datetime.date(2026, 1, 15)
    assert refreshed.next_run_on == datetime.date(2026, 2, 15)

    # The invoice exists
    invoice = (await db_session.execute(select(Invoice).where(Invoice.id == run.generated_invoice_id))).scalar_one()
    assert invoice.subtotal == Decimal("100.00")
    assert invoice.total_due == Decimal("100.00")
    assert invoice.invoice_number.startswith("INV-")


@pytest.mark.asyncio
async def test_skip_next_advances_without_invoice(db_session):
    c = await _customer(db_session)
    r = await _rule(db_session, c.id)
    run = await skip_next(db_session, r.id)
    assert run.status == "skipped"
    assert run.generated_invoice_id is None
    refreshed = (await db_session.execute(select(RecurringInvoice).where(RecurringInvoice.id == r.id))).scalar_one()
    assert refreshed.next_run_on == datetime.date(2026, 2, 15)


@pytest.mark.asyncio
async def test_paused_rule_run_one_rejected(db_session):
    c = await _customer(db_session)
    r = await _rule(db_session, c.id)
    r.is_active = False
    await db_session.flush()
    with pytest.raises(RecurringInvoiceError):
        await run_one(db_session, recurring_id=r.id)


@pytest.mark.asyncio
async def test_failure_does_not_advance(db_session):
    c = await _customer(db_session)
    r = await _rule(db_session, c.id)
    # Wipe template so generation raises
    r.line_items_template = []
    await db_session.flush()

    run = await run_one(db_session, recurring_id=r.id)
    assert run.status == "failed"
    refreshed = (await db_session.execute(select(RecurringInvoice).where(RecurringInvoice.id == r.id))).scalar_one()
    # next_run_on unchanged
    assert refreshed.next_run_on == datetime.date(2026, 1, 15)
    assert refreshed.last_error is not None


@pytest.mark.asyncio
async def test_end_on_auto_deactivates(db_session):
    c = await _customer(db_session)
    r = await _rule(
        db_session, c.id,
        start=datetime.date(2026, 1, 15),
        end=datetime.date(2026, 2, 1),
    )
    run = await run_one(db_session, recurring_id=r.id)
    assert run.status == "succeeded"
    refreshed = (await db_session.execute(select(RecurringInvoice).where(RecurringInvoice.id == r.id))).scalar_one()
    # next_run_on (2026-02-15) > end_on → auto-deactivated
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_run_due_picks_up_due_rules(db_session):
    c = await _customer(db_session)
    # Two due, one not yet due
    await _rule(db_session, c.id, start=datetime.date(2026, 1, 1))
    await _rule(db_session, c.id, start=datetime.date(2026, 1, 10))
    await _rule(db_session, c.id, start=datetime.date(2026, 6, 1))  # future
    summary = await run_due(db_session, today=datetime.date(2026, 1, 31))
    assert summary["considered"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0


@pytest.mark.asyncio
async def test_run_due_idempotent_within_day(db_session):
    c = await _customer(db_session)
    await _rule(db_session, c.id, start=datetime.date(2026, 1, 15))
    s1 = await run_due(db_session, today=datetime.date(2026, 1, 15))
    s2 = await run_due(db_session, today=datetime.date(2026, 1, 15))
    assert s1["succeeded"] == 1
    assert s2["considered"] == 0
