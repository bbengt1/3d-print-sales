"""#270 P1 (Codex): failed-delivery EmailDelivery rows must survive the 502.

Before the fix, the invoice/quote email endpoints raised an HTTPException on
``EmailSendError`` without committing the transaction. ``send_email`` only
flushes the failed ``EmailDelivery`` row, and ``get_db`` simply closes the
session on the way out, which rolls the flush back — so the audit row that
was supposed to record ``status='failed'`` was lost.

These tests drive the API endpoints with a patched SMTP that raises, then
re-open the DB to confirm the failed audit row is actually persisted.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.email_delivery import EmailDelivery
from app.models.invoice import Invoice
from app.models.material import Material
from app.models.quote import Quote
from app.models.setting import Setting


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
    await db_session.commit()


async def _seed_invoice(db_session) -> Invoice:
    inv = Invoice(
        invoice_number="INV-P1-270-1",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("0.00"),
        shipping_amount=Decimal("0.00"),
        credits_applied=Decimal("0.00"),
        total_due=Decimal("100.00"),
        amount_paid=Decimal("0.00"),
        balance_due=Decimal("100.00"),
        customer_name="Audit Customer",
        status="sent",
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)
    return inv


async def _seed_quote(db_session) -> Quote:
    mat = Material(
        name="PLA-P1-270",
        brand="Generic",
        spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"),
        net_usable_g=Decimal("950"),
        cost_per_g=Decimal("20") / Decimal("950"),
    )
    db_session.add(mat)
    await db_session.commit()
    await db_session.refresh(mat)

    q = Quote(
        quote_number="Q-P1-270-1",
        date=date.today(),
        valid_until=date.today() + timedelta(days=30),
        customer_name="Audit Customer",
        product_name="Custom Bracket",
        qty_per_plate=2,
        num_plates=2,
        material_id=mat.id,
        total_pieces=4,
        material_per_plate_g=Decimal("50"),
        print_time_per_plate_hrs=Decimal("2"),
        total_revenue=Decimal("100"),
        status="accepted",
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)
    return q


@pytest.mark.asyncio
async def test_invoice_email_send_failure_persists_audit_row(
    client, auth_headers, db_session
):
    await _seed_smtp_settings(db_session)
    invoice = await _seed_invoice(db_session)

    mock_server = MagicMock()
    mock_server.send_message.side_effect = RuntimeError("smtp boom")
    with patch("app.services.email_service.smtplib.SMTP", return_value=mock_server):
        resp = await client.post(
            f"/api/v1/invoices/{invoice.id}/email",
            headers=auth_headers,
            json={"to_email": "audit@example.com"},
        )
    assert resp.status_code == 502, resp.text

    # Re-query in the test session to verify the failed row was actually
    # committed by the endpoint (not just flushed and rolled back).
    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(EmailDelivery).where(EmailDelivery.scope == "invoice")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].to_email == "audit@example.com"
    assert "smtp boom" in (rows[0].error or "")


@pytest.mark.asyncio
async def test_quote_email_send_failure_persists_audit_row(
    client, auth_headers, db_session
):
    await _seed_smtp_settings(db_session)
    quote = await _seed_quote(db_session)

    mock_server = MagicMock()
    mock_server.send_message.side_effect = RuntimeError("smtp boom")
    with patch("app.services.email_service.smtplib.SMTP", return_value=mock_server):
        resp = await client.post(
            f"/api/v1/quotes/{quote.id}/email",
            headers=auth_headers,
            json={"to_email": "audit@example.com"},
        )
    assert resp.status_code == 502, resp.text

    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(EmailDelivery).where(EmailDelivery.scope == "quote")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].to_email == "audit@example.com"
    assert "smtp boom" in (rows[0].error or "")
