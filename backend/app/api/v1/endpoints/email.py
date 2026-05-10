from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.customer import Customer
from app.models.email_delivery import EmailDelivery
from app.models.invoice import Invoice
from app.models.quote import Quote
from app.models.setting import Setting
from app.services.email_service import (
    EmailConfigError,
    EmailSendError,
    render_invoice_template,
    render_quote_template,
    send_email,
)


router = APIRouter(tags=["Email"])


class EmailSendRequest(BaseModel):
    to_email: EmailStr | None = None
    cc: list[EmailStr] = Field(default_factory=list)
    bcc: list[EmailStr] = Field(default_factory=list)
    subject_override: str | None = Field(None, max_length=500)


class EmailDeliveryResponse(BaseModel):
    id: uuid.UUID
    scope: str
    record_id: uuid.UUID
    to_email: str
    from_email: str
    from_name: str
    subject: str
    transport: str
    provider_message_id: str | None
    status: str
    sent_at: str | None
    error: str | None

    @classmethod
    def from_model(cls, m: EmailDelivery) -> "EmailDeliveryResponse":
        return cls(
            id=m.id,
            scope=m.scope,
            record_id=m.record_id,
            to_email=m.to_email,
            from_email=m.from_email,
            from_name=m.from_name,
            subject=m.subject,
            transport=m.transport,
            provider_message_id=m.provider_message_id,
            status=m.status,
            sent_at=m.sent_at.isoformat() if m.sent_at else None,
            error=m.error,
        )


async def _resolve_customer_name(db, customer_id, fallback) -> tuple[str, str | None]:
    """Returns (to_email_or_empty, customer_name_or_none)."""
    if not customer_id:
        return "", fallback
    row = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if not row:
        return "", fallback
    return (row.email or ""), (row.name or fallback)


async def _business_name(db) -> str:
    row = (await db.execute(select(Setting).where(Setting.key == "business_name"))).scalar_one_or_none()
    return (row.value if row else "").strip() or "Your Business"


@router.post(
    "/invoices/{invoice_id}/email",
    response_model=EmailDeliveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Send an invoice via email",
)
async def email_invoice(invoice_id: uuid.UUID, body: EmailSendRequest, user: CurrentUser, db: DB):
    invoice = (await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.is_deleted == False))).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    customer_email, customer_name = await _resolve_customer_name(db, invoice.customer_id, invoice.customer_name)
    to_email = body.to_email or customer_email
    if not to_email:
        raise HTTPException(status_code=400, detail="No to_email supplied and customer has no email on file")

    business_name = await _business_name(db)
    subject, body_text, body_html = await render_invoice_template(invoice, business_name, customer_name, db=db)
    if body.subject_override:
        subject = body.subject_override

    try:
        delivery = await send_email(
            db,
            scope="invoice",
            record_id=invoice.id,
            to_email=str(to_email),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            cc=[str(c) for c in body.cc],
            bcc=[str(c) for c in body.bcc],
            sent_by_user_id=user.id,
        )
    except EmailConfigError as e:
        raise HTTPException(status_code=400, detail=f"Email transport not configured: {e}") from e
    except EmailSendError as e:
        # send_email already flushed the failed delivery row; commit it so the
        # audit trail survives the 502 response (otherwise the get_db session
        # close rolls it back and we lose the status='failed' record).
        await db.commit()
        raise HTTPException(status_code=502, detail=f"SMTP send failed: {e}") from e

    await db.commit()
    return EmailDeliveryResponse.from_model(delivery)


@router.post(
    "/quotes/{quote_id}/email",
    response_model=EmailDeliveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a quote via email",
)
async def email_quote(quote_id: uuid.UUID, body: EmailSendRequest, user: CurrentUser, db: DB):
    quote = (await db.execute(select(Quote).where(Quote.id == quote_id, Quote.is_deleted == False))).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    customer_email, customer_name = await _resolve_customer_name(db, quote.customer_id, quote.customer_name)
    to_email = body.to_email or customer_email
    if not to_email:
        raise HTTPException(status_code=400, detail="No to_email supplied and customer has no email on file")

    business_name = await _business_name(db)
    subject, body_text, body_html = await render_quote_template(quote, business_name, customer_name, db=db)
    if body.subject_override:
        subject = body.subject_override

    try:
        delivery = await send_email(
            db,
            scope="quote",
            record_id=quote.id,
            to_email=str(to_email),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            cc=[str(c) for c in body.cc],
            bcc=[str(c) for c in body.bcc],
            sent_by_user_id=user.id,
        )
    except EmailConfigError as e:
        raise HTTPException(status_code=400, detail=f"Email transport not configured: {e}") from e
    except EmailSendError as e:
        # send_email already flushed the failed delivery row; commit it so the
        # audit trail survives the 502 response (otherwise the get_db session
        # close rolls it back and we lose the status='failed' record).
        await db.commit()
        raise HTTPException(status_code=502, detail=f"SMTP send failed: {e}") from e

    await db.commit()
    return EmailDeliveryResponse.from_model(delivery)


@router.get(
    "/invoices/{invoice_id}/email-deliveries",
    response_model=list[EmailDeliveryResponse],
    summary="List email send history for an invoice",
)
async def list_invoice_deliveries(invoice_id: uuid.UUID, user: CurrentUser, db: DB):
    rows = (
        await db.execute(
            select(EmailDelivery)
            .where(EmailDelivery.scope == "invoice", EmailDelivery.record_id == invoice_id)
            .order_by(EmailDelivery.created_at.desc())
        )
    ).scalars().all()
    return [EmailDeliveryResponse.from_model(r) for r in rows]


@router.get(
    "/quotes/{quote_id}/email-deliveries",
    response_model=list[EmailDeliveryResponse],
    summary="List email send history for a quote",
)
async def list_quote_deliveries(quote_id: uuid.UUID, user: CurrentUser, db: DB):
    rows = (
        await db.execute(
            select(EmailDelivery)
            .where(EmailDelivery.scope == "quote", EmailDelivery.record_id == quote_id)
            .order_by(EmailDelivery.created_at.desc())
        )
    ).scalars().all()
    return [EmailDeliveryResponse.from_model(r) for r in rows]
