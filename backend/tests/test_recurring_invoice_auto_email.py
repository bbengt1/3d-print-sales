from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.customer import Customer
from app.models.email_delivery import EmailDelivery
from app.models.recurring_invoice import RecurringInvoice
from app.models.setting import Setting
from app.services.recurring_invoice_service import run_one


async def _seed_smtp_settings(db_session):
    rows = [
        ("email_smtp_host", "smtp.example.com"),
        ("email_smtp_port", "587"),
        ("email_smtp_username", "user"),
        ("email_smtp_password", "pw"),
        ("email_smtp_use_tls", "true"),
        ("email_from_address", "noreply@example.com"),
        ("email_from_name", "Test Shop"),
        ("business_name", "Test Shop"),
    ]
    for k, v in rows:
        db_session.add(Setting(key=k, value=v))
    await db_session.flush()


async def _customer_with_email(db_session, email="customer@x.com") -> Customer:
    c = Customer(name="ARClient", email=email)
    db_session.add(c)
    await db_session.flush()
    return c


async def _rule(db_session, customer_id, *, auto_email: bool, start=datetime.date(2026, 1, 15)):
    r = RecurringInvoice(
        name="Monthly retainer",
        customer_id=customer_id,
        cadence="monthly",
        interval_count=1,
        start_on=start,
        next_run_on=start,
        auto_email=auto_email,
        line_items_template=[
            {"description": "Retainer", "quantity": 1, "unit_price": "100.00"},
        ],
        due_in_days=30,
    )
    db_session.add(r)
    await db_session.flush()
    return r


@pytest.mark.asyncio
async def test_auto_email_off_skips_send(db_session):
    await _seed_smtp_settings(db_session)
    c = await _customer_with_email(db_session)
    r = await _rule(db_session, c.id, auto_email=False)
    with patch("smtplib.SMTP") as m:
        run = await run_one(db_session, recurring_id=r.id)
    assert run.status == "succeeded"
    # No email delivery row — auto_email was off
    rows = (await db_session.execute(select(EmailDelivery))).scalars().all()
    assert len(rows) == 0
    m.assert_not_called()


@pytest.mark.asyncio
async def test_auto_email_on_sends_via_smtp(db_session):
    await _seed_smtp_settings(db_session)
    c = await _customer_with_email(db_session)
    r = await _rule(db_session, c.id, auto_email=True)

    mock_server = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_server):
        run = await run_one(db_session, recurring_id=r.id)
    assert run.status == "succeeded"
    rows = (await db_session.execute(select(EmailDelivery))).scalars().all()
    assert len(rows) == 1
    assert rows[0].to_email == "customer@x.com"
    assert rows[0].status == "sent"


@pytest.mark.asyncio
async def test_auto_email_with_no_customer_email_records_error(db_session):
    await _seed_smtp_settings(db_session)
    c = Customer(name="NoEmail", email=None)
    db_session.add(c)
    await db_session.flush()
    r = await _rule(db_session, c.id, auto_email=True)
    run = await run_one(db_session, recurring_id=r.id)
    # Invoice still generated successfully, but email path records an error
    assert run.status == "succeeded"
    refreshed = (await db_session.execute(select(RecurringInvoice).where(RecurringInvoice.id == r.id))).scalar_one()
    assert "no email on file" in (refreshed.last_error or "")


@pytest.mark.asyncio
async def test_email_failure_does_not_roll_back_invoice(db_session):
    await _seed_smtp_settings(db_session)
    c = await _customer_with_email(db_session)
    r = await _rule(db_session, c.id, auto_email=True)

    mock_server = MagicMock()
    mock_server.send_message.side_effect = RuntimeError("smtp down")
    with patch("smtplib.SMTP", return_value=mock_server):
        run = await run_one(db_session, recurring_id=r.id)
    # Run still succeeded — invoice was generated even though email failed
    assert run.status == "succeeded"
    assert run.generated_invoice_id is not None
    # Last error recorded on the rule
    refreshed = (await db_session.execute(select(RecurringInvoice).where(RecurringInvoice.id == r.id))).scalar_one()
    assert "email send failed" in (refreshed.last_error or "")
