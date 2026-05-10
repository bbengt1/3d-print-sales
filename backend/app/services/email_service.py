"""Outbound transactional email — Phase 1 of #244.

Phase 1 ships SMTP send for invoices and quotes with HTML+text body. PDF
attachment (WeasyPrint), Resend transport, opens-tracking, and webhook
signature verification are deferred to follow-up issues so the Docker
image doesn't need cairo/pango/svix dependencies in this PR.

Templates are hard-coded in this module for Phase 1; promoting them to
operator-editable settings is a Phase 2 follow-up.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_delivery import EmailDelivery
from app.models.invoice import Invoice
from app.models.quote import Quote
from app.models.setting import Setting

log = logging.getLogger(__name__)

EmailScope = Literal["invoice", "quote"]


class EmailConfigError(RuntimeError):
    """Raised when SMTP settings are missing or invalid."""


class EmailSendError(RuntimeError):
    """Raised when the SMTP transport returns an error."""


@dataclass
class EmailMessagePayload:
    to: list[str]
    from_address: str
    from_name: str
    subject: str
    body_text: str
    body_html: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)


@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    use_tls: bool
    from_address: str
    from_name: str


async def _load_setting(db: AsyncSession, key: str) -> str:
    row = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    return row.value if row else ""


async def load_smtp_config(db: AsyncSession) -> SmtpConfig:
    keys = [
        "email_smtp_host",
        "email_smtp_port",
        "email_smtp_username",
        "email_smtp_password",
        "email_smtp_use_tls",
        "email_from_address",
        "email_from_name",
    ]
    values = {k: await _load_setting(db, k) for k in keys}
    host = values["email_smtp_host"].strip()
    from_address = values["email_from_address"].strip()
    if not host:
        raise EmailConfigError("email_smtp_host is not set")
    if not from_address:
        raise EmailConfigError("email_from_address is not set")
    try:
        port = int(values["email_smtp_port"] or "587")
    except ValueError as e:
        raise EmailConfigError(f"email_smtp_port must be an integer: {e}") from e
    return SmtpConfig(
        host=host,
        port=port,
        username=values["email_smtp_username"].strip() or None,
        password=values["email_smtp_password"] or None,
        use_tls=values["email_smtp_use_tls"].strip().lower() in ("true", "1", "yes"),
        from_address=from_address,
        from_name=values["email_from_name"].strip() or from_address,
    )


def _build_mime(payload: EmailMessagePayload) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{payload.from_name} <{payload.from_address}>"
    msg["To"] = ", ".join(payload.to)
    if payload.cc:
        msg["Cc"] = ", ".join(payload.cc)
    msg["Subject"] = payload.subject
    msg.set_content(payload.body_text)
    msg.add_alternative(payload.body_html, subtype="html")
    return msg


def _smtp_send_blocking(config: SmtpConfig, payload: EmailMessagePayload) -> str:
    """Run synchronously inside `asyncio.to_thread`. Returns the Message-ID
    header that the server (or our composed MIME) carries — we use it as the
    provider_message_id for the audit trail.
    """
    msg = _build_mime(payload)
    server: smtplib.SMTP
    if config.use_tls:
        server = smtplib.SMTP(config.host, config.port, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP(config.host, config.port, timeout=30)
    try:
        if config.username and config.password:
            server.login(config.username, config.password)
        all_rcpts = list(payload.to) + list(payload.cc) + list(payload.bcc)
        server.send_message(msg, from_addr=config.from_address, to_addrs=all_rcpts)
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001
            server.close()
    return msg.get("Message-ID", "")


# ---------- Templates (Phase 1: hard-coded, edit-via-code) ----------

INVOICE_SUBJECT = "Invoice {invoice_number} from {business_name}"
INVOICE_BODY_TEXT = """Hi{name_clause},

Please find your invoice {invoice_number} below.

Total: {total}
Issue date: {issue_date}
Due date: {due_date}

Thank you,
{business_name}
"""
INVOICE_BODY_HTML = """\
<!doctype html>
<html><body style="font-family: -apple-system, system-ui, Segoe UI, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #111;">Invoice {invoice_number}</h2>
<p>Hi{name_clause},</p>
<p>Please find your invoice details below:</p>
<table style="border-collapse: collapse; margin: 1em 0;">
<tr><td style="padding: 4px 12px;"><strong>Issue date</strong></td><td style="padding: 4px 12px;">{issue_date}</td></tr>
<tr><td style="padding: 4px 12px;"><strong>Due date</strong></td><td style="padding: 4px 12px;">{due_date}</td></tr>
<tr><td style="padding: 4px 12px;"><strong>Total</strong></td><td style="padding: 4px 12px;">{total}</td></tr>
</table>
<p>Thank you,<br/>{business_name}</p>
</body></html>
"""

QUOTE_SUBJECT = "Quote {quote_number} from {business_name}"
QUOTE_BODY_TEXT = """Hi{name_clause},

Please find your quote {quote_number} below.

Product: {product_name}
Total: {total}
Valid until: {valid_until}

Thank you,
{business_name}
"""
QUOTE_BODY_HTML = """\
<!doctype html>
<html><body style="font-family: -apple-system, system-ui, Segoe UI, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #111;">Quote {quote_number}</h2>
<p>Hi{name_clause},</p>
<p>Please find your quote details below:</p>
<table style="border-collapse: collapse; margin: 1em 0;">
<tr><td style="padding: 4px 12px;"><strong>Product</strong></td><td style="padding: 4px 12px;">{product_name}</td></tr>
<tr><td style="padding: 4px 12px;"><strong>Total</strong></td><td style="padding: 4px 12px;">{total}</td></tr>
<tr><td style="padding: 4px 12px;"><strong>Valid until</strong></td><td style="padding: 4px 12px;">{valid_until}</td></tr>
</table>
<p>Thank you,<br/>{business_name}</p>
</body></html>
"""


def _name_clause(name: str | None) -> str:
    return f" {name}" if name and name.strip() else ""


async def _maybe_override(db: AsyncSession | None, key: str, default: str) -> str:
    """#320 P2: optional Settings-table override for an email template part.

    The setting key conventions are:
      email.invoice.subject / email.invoice.body_text / email.invoice.body_html
      email.quote.subject / email.quote.body_text / email.quote.body_html
    Operators leave them unset to keep defaults; setting them to a non-empty
    value substitutes that string. The same `{placeholders}` are available
    as in the defaults — `format(**ctx)` is applied after lookup.
    """
    if db is None:
        return default
    from app.models.setting import Setting

    row = (
        await db.execute(select(Setting).where(Setting.key == key))
    ).scalar_one_or_none()
    if row is None:
        return default
    val = (row.value or "").strip()
    return val if val else default


async def render_invoice_template(
    invoice: Invoice,
    business_name: str,
    customer_name: str | None,
    *,
    db: AsyncSession | None = None,
) -> tuple[str, str, str]:
    ctx = {
        "invoice_number": invoice.invoice_number,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else "",
        "due_date": invoice.due_date.isoformat() if invoice.due_date else "n/a",
        "total": f"${invoice.total_due:,.2f}" if invoice.total_due is not None else "",
        "business_name": business_name,
        "name_clause": _name_clause(customer_name),
    }
    subject_t = await _maybe_override(db, "email.invoice.subject", INVOICE_SUBJECT)
    text_t = await _maybe_override(db, "email.invoice.body_text", INVOICE_BODY_TEXT)
    html_t = await _maybe_override(db, "email.invoice.body_html", INVOICE_BODY_HTML)
    return (
        subject_t.format(**ctx),
        text_t.format(**ctx),
        html_t.format(**ctx),
    )


async def render_quote_template(
    quote: Quote,
    business_name: str,
    customer_name: str | None,
    *,
    db: AsyncSession | None = None,
) -> tuple[str, str, str]:
    ctx = {
        "quote_number": quote.quote_number,
        "product_name": quote.product_name or "",
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else "n/a",
        "total": f"${quote.total_revenue:,.2f}" if getattr(quote, "total_revenue", None) is not None else "",
        "business_name": business_name,
        "name_clause": _name_clause(customer_name),
    }
    subject_t = await _maybe_override(db, "email.quote.subject", QUOTE_SUBJECT)
    text_t = await _maybe_override(db, "email.quote.body_text", QUOTE_BODY_TEXT)
    html_t = await _maybe_override(db, "email.quote.body_html", QUOTE_BODY_HTML)
    return (
        subject_t.format(**ctx),
        text_t.format(**ctx),
        html_t.format(**ctx),
    )


# ---------- Send + audit ----------

async def send_email(
    db: AsyncSession,
    *,
    scope: EmailScope,
    record_id: uuid.UUID,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    sent_by_user_id: uuid.UUID | None = None,
) -> EmailDelivery:
    """Send and persist an EmailDelivery row regardless of outcome."""
    config = await load_smtp_config(db)
    payload = EmailMessagePayload(
        to=[to_email],
        from_address=config.from_address,
        from_name=config.from_name,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        cc=cc or [],
        bcc=bcc or [],
    )

    delivery = EmailDelivery(
        scope=scope,
        record_id=record_id,
        to_email=to_email,
        cc=", ".join(payload.cc) if payload.cc else None,
        bcc=", ".join(payload.bcc) if payload.bcc else None,
        from_email=config.from_address,
        from_name=config.from_name,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        transport="smtp",
        status="pending",
        sent_by_user_id=sent_by_user_id,
    )
    db.add(delivery)
    await db.flush()

    try:
        message_id = await asyncio.to_thread(_smtp_send_blocking, config, payload)
    except Exception as e:  # noqa: BLE001
        delivery.status = "failed"
        delivery.error = f"{type(e).__name__}: {e}"
        await db.flush()
        log.exception("email send failed", extra={"scope": scope, "record_id": str(record_id)})
        raise EmailSendError(str(e)) from e

    delivery.status = "sent"
    delivery.sent_at = datetime.now(timezone.utc)
    delivery.provider_message_id = message_id or None
    await db.flush()
    return delivery
