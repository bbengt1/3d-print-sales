from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.email_delivery import EmailDelivery
from app.models.invoice import Invoice
from app.models.setting import Setting
from app.services.email_service import (
    EmailConfigError,
    EmailSendError,
    load_smtp_config,
    render_invoice_template,
    send_email,
)


async def _seed_smtp_settings(db_session):
    rows = [
        ("email_transport", "smtp"),
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


@pytest.mark.asyncio
async def test_load_smtp_config_happy(db_session):
    await _seed_smtp_settings(db_session)
    cfg = await load_smtp_config(db_session)
    assert cfg.host == "smtp.example.com"
    assert cfg.port == 587
    assert cfg.username == "user"
    assert cfg.use_tls is True
    assert cfg.from_address == "noreply@example.com"
    assert cfg.from_name == "Test Shop"


@pytest.mark.asyncio
async def test_load_smtp_config_missing_host_raises(db_session):
    db_session.add(Setting(key="email_smtp_host", value=""))
    db_session.add(Setting(key="email_from_address", value="x@y.z"))
    await db_session.commit()
    with pytest.raises(EmailConfigError):
        await load_smtp_config(db_session)


def test_render_invoice_template_substitutes_fields():
    invoice = Invoice(
        id=None,
        invoice_number="INV-2026-0001",
        issue_date=datetime.date(2026, 5, 1),
        due_date=datetime.date(2026, 5, 31),
        subtotal=Decimal("100"),
        tax_amount=Decimal("8"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("108"),
        amount_paid=Decimal("0"),
    )
    subject, body_text, body_html = render_invoice_template(invoice, "Test Shop", "Alice")
    assert "INV-2026-0001" in subject
    assert "Test Shop" in subject
    assert "Alice" in body_text
    assert "$108.00" in body_text
    assert "INV-2026-0001" in body_html
    assert "$108.00" in body_html


@pytest.mark.asyncio
async def test_send_email_persists_sent_row_and_calls_smtp(db_session):
    await _seed_smtp_settings(db_session)

    mock_server = MagicMock()
    mock_server.get.return_value = "<msg-1@test>"
    with patch("app.services.email_service.smtplib.SMTP", return_value=mock_server):
        delivery = await send_email(
            db_session,
            scope="invoice",
            record_id=__import__("uuid").uuid4(),
            to_email="customer@example.com",
            subject="Test",
            body_text="text body",
            body_html="<p>html body</p>",
        )
    await db_session.commit()

    rows = (await db_session.execute(select(EmailDelivery))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "sent"
    assert rows[0].to_email == "customer@example.com"
    assert rows[0].sent_at is not None
    mock_server.send_message.assert_called_once()
    mock_server.quit.assert_called()


@pytest.mark.asyncio
async def test_send_email_records_failure_and_raises(db_session):
    await _seed_smtp_settings(db_session)

    mock_server = MagicMock()
    mock_server.send_message.side_effect = RuntimeError("connection refused")
    with patch("app.services.email_service.smtplib.SMTP", return_value=mock_server):
        with pytest.raises(EmailSendError):
            await send_email(
                db_session,
                scope="invoice",
                record_id=__import__("uuid").uuid4(),
                to_email="customer@example.com",
                subject="Test",
                body_text="text body",
                body_html="<p>html</p>",
            )
    await db_session.commit()

    rows = (await db_session.execute(select(EmailDelivery))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert "connection refused" in (rows[0].error or "")
