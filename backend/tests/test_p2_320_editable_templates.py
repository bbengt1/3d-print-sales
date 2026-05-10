"""#320 P2: editable email templates via Setting overrides."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from app.models.invoice import Invoice
from app.models.setting import Setting
from app.services.email_service import render_invoice_template


@pytest.mark.asyncio
async def test_invoice_subject_override_kicks_in(db_session):
    db_session.add(
        Setting(
            key="email.invoice.subject",
            value="Custom: {invoice_number} -- thanks!",
            notes=None,
        )
    )
    await db_session.commit()
    invoice = Invoice(
        id=None,
        invoice_number="INV-X",
        issue_date=datetime.date(2026, 5, 1),
        due_date=datetime.date(2026, 5, 31),
        subtotal=Decimal("10"),
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("10"),
        amount_paid=Decimal("0"),
    )
    subject, _, _ = await render_invoice_template(invoice, "Biz", "Alice", db=db_session)
    assert subject == "Custom: INV-X -- thanks!"


@pytest.mark.asyncio
async def test_invoice_no_override_uses_default(db_session):
    invoice = Invoice(
        id=None,
        invoice_number="INV-Y",
        issue_date=datetime.date(2026, 5, 1),
        due_date=datetime.date(2026, 5, 31),
        subtotal=Decimal("10"),
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("10"),
        amount_paid=Decimal("0"),
    )
    subject, _, _ = await render_invoice_template(invoice, "Biz", "Alice", db=db_session)
    assert subject == "Invoice INV-Y from Biz"


@pytest.mark.asyncio
async def test_long_template_value_persists(db_session):
    """Setting.value is now TEXT — verify a long template body round-trips."""
    long_html = "<p>" + ("x" * 5000) + "</p>"
    db_session.add(Setting(key="email.invoice.body_html", value=long_html, notes=None))
    await db_session.commit()
    from sqlalchemy import select

    row = (
        await db_session.execute(select(Setting).where(Setting.key == "email.invoice.body_html"))
    ).scalar_one()
    assert len(row.value) > 4000
