from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.quote import Quote
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceCreditApply,
    InvoiceFromQuoteCreate,
    InvoicePaymentApply,
    InvoiceResponse,
    InvoiceStatus,
    InvoiceUpdate,
    PaginatedInvoices,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _derive_invoice_status(invoice: Invoice, as_of: datetime.date | None = None) -> str:
    if invoice.status == "void":
        return "void"
    if invoice.balance_due <= 0:
        return "paid"
    if invoice.amount_paid > 0:
        return "partially_paid"
    if invoice.due_date and (as_of or datetime.date.today()) > invoice.due_date:
        return "overdue"
    if invoice.status == "sent":
        return "sent"
    return "draft"


def _recalculate_invoice(invoice: Invoice) -> None:
    subtotal = sum((line.line_total for line in invoice.lines), Decimal("0"))
    invoice.subtotal = subtotal
    invoice.total_due = subtotal + invoice.tax_amount + invoice.shipping_amount - invoice.credits_applied
    if invoice.total_due < 0:
        raise HTTPException(status_code=400, detail="Credits cannot exceed invoice gross amount")
    invoice.balance_due = invoice.total_due - invoice.amount_paid
    if invoice.balance_due < 0:
        raise HTTPException(status_code=400, detail="Amount paid exceeds total due")
    invoice.status = _derive_invoice_status(invoice)


async def _get_invoice(db: DB, invoice_id: uuid.UUID) -> Invoice | None:
    result = await db.execute(select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.id == invoice_id, Invoice.is_deleted == False))
    return result.scalar_one_or_none()


@router.get("", response_model=PaginatedInvoices, summary="List invoices")
async def list_invoices(
    db: DB,
    status: InvoiceStatus | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    base = select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.is_deleted == False)
    if status:
        base = base.where(Invoice.status == status.value)
    if customer_id:
        base = base.where(Invoice.customer_id == customer_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    result = await db.execute(base.order_by(Invoice.issue_date.desc(), Invoice.created_at.desc()).offset(skip).limit(limit))
    return PaginatedInvoices(items=result.scalars().all(), total=total, skip=skip, limit=limit)


@router.get("/{invoice_id}", response_model=InvoiceResponse, summary="Get invoice by ID")
async def get_invoice(invoice_id: uuid.UUID, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = _derive_invoice_status(invoice)
    await db.commit()
    return invoice


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Create invoice")
async def create_invoice(body: InvoiceCreate, user: CurrentUser, db: DB):
    existing = await db.execute(select(Invoice.id).where(Invoice.invoice_number == body.invoice_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Invoice number '{body.invoice_number}' already exists")

    invoice = Invoice(
        invoice_number=body.invoice_number,
        quote_id=body.quote_id,
        customer_id=body.customer_id,
        customer_name=body.customer_name,
        issue_date=body.issue_date,
        due_date=body.due_date,
        tax_amount=body.tax_amount,
        shipping_amount=body.shipping_amount,
        credits_applied=body.credits_applied,
        notes=body.notes,
        status=body.status.value,
    )
    db.add(invoice)
    await db.flush()

    for line in body.lines:
        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.quantity * line.unit_price,
                notes=line.notes,
            )
        )
    await db.flush()
    await db.refresh(invoice, attribute_names=["lines"])
    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.post("/from-quote/{quote_id}", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Create invoice from accepted quote")
async def create_invoice_from_quote(quote_id: uuid.UUID, body: InvoiceFromQuoteCreate, user: CurrentUser, db: DB):
    quote = (await db.execute(select(Quote).where(Quote.id == quote_id, Quote.is_deleted == False))).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status != "accepted":
        raise HTTPException(status_code=400, detail="Only accepted quotes can be invoiced")

    existing = await db.execute(select(Invoice.id).where(Invoice.invoice_number == body.invoice_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Invoice number '{body.invoice_number}' already exists")

    invoice = Invoice(
        invoice_number=body.invoice_number,
        quote_id=quote.id,
        customer_id=quote.customer_id,
        customer_name=quote.customer_name,
        issue_date=body.issue_date,
        due_date=body.due_date,
        tax_amount=body.tax_amount,
        shipping_amount=body.shipping_amount if body.shipping_amount is not None else quote.shipping_cost,
        credits_applied=body.credits_applied,
        notes=body.notes or quote.notes,
        status=body.status.value,
    )
    db.add(invoice)
    await db.flush()

    db.add(
        InvoiceLine(
            invoice_id=invoice.id,
            description=quote.product_name,
            quantity=quote.total_pieces,
            unit_price=quote.price_per_piece,
            line_total=quote.total_revenue,
            notes=f"Generated from quote {quote.quote_number}",
        )
    )
    await db.flush()
    await db.refresh(invoice, attribute_names=["lines"])
    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.put("/{invoice_id}", response_model=InvoiceResponse, summary="Update invoice")
async def update_invoice(invoice_id: uuid.UUID, body: InvoiceUpdate, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "status":
            invoice.status = value.value if hasattr(value, "value") else value
        else:
            setattr(invoice, field, value)
    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.post("/{invoice_id}/apply-payment", response_model=InvoiceResponse, summary="Apply payment to invoice")
async def apply_invoice_payment(invoice_id: uuid.UUID, body: InvoicePaymentApply, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot apply payment to void invoice")
    invoice.amount_paid = invoice.amount_paid + body.amount
    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.post("/{invoice_id}/apply-credit", response_model=InvoiceResponse, summary="Apply credit to invoice")
async def apply_invoice_credit(invoice_id: uuid.UUID, body: InvoiceCreditApply, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot apply credit to void invoice")
    invoice.credits_applied = invoice.credits_applied + body.amount
    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.delete("/{invoice_id}", status_code=204, summary="Delete invoice")
async def delete_invoice(invoice_id: uuid.UUID, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.is_deleted = True
    await db.commit()
