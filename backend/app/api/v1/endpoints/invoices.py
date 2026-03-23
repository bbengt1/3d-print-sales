from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.models.customer_credit import CustomerCredit
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.payment import Payment
from app.models.quote import Quote
from app.schemas.ar import (
    ARAgingRow,
    ARAgingSummary,
    CustomerCreditApply,
    CustomerCreditCreate,
    CustomerCreditResponse,
    PaymentCreate,
    PaymentResponse,
)
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


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, summary="Record payment")
async def record_payment(body: PaymentCreate, user: CurrentUser, db: DB):
    if body.invoice_id:
        invoice = await _get_invoice(db, body.invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.status == "void":
            raise HTTPException(status_code=400, detail="Cannot apply payment to void invoice")
        if body.amount > invoice.balance_due:
            unapplied = body.amount - invoice.balance_due
            applied = invoice.balance_due
        else:
            unapplied = Decimal("0")
            applied = body.amount
        invoice.amount_paid = invoice.amount_paid + applied
        _recalculate_invoice(invoice)
        payment = Payment(
            customer_id=body.customer_id or invoice.customer_id,
            invoice_id=invoice.id,
            payment_date=body.payment_date,
            amount=body.amount,
            payment_method=body.payment_method,
            reference_number=body.reference_number,
            notes=body.notes,
            unapplied_amount=unapplied,
        )
    else:
        payment = Payment(**body.model_dump(), unapplied_amount=body.amount)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.post("/{invoice_id}/apply-payment", response_model=InvoiceResponse, summary="Apply payment to invoice")
async def apply_invoice_payment(invoice_id: uuid.UUID, body: InvoicePaymentApply, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot apply payment to void invoice")
    payment = Payment(
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        payment_date=body.paid_at or datetime.date.today(),
        amount=body.amount,
        unapplied_amount=Decimal("0"),
    )
    db.add(payment)
    invoice.amount_paid = invoice.amount_paid + body.amount
    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.post("/credits", response_model=CustomerCreditResponse, status_code=status.HTTP_201_CREATED, summary="Create customer credit")
async def create_customer_credit(body: CustomerCreditCreate, user: CurrentUser, db: DB):
    credit = CustomerCredit(
        customer_id=body.customer_id,
        invoice_id=body.invoice_id,
        credit_date=body.credit_date,
        amount=body.amount,
        remaining_amount=body.amount,
        reason=body.reason,
        notes=body.notes,
    )
    db.add(credit)
    await db.commit()
    await db.refresh(credit)
    return credit


@router.post("/{invoice_id}/apply-credit", response_model=InvoiceResponse, summary="Apply credit to invoice")
async def apply_invoice_credit(invoice_id: uuid.UUID, body: CustomerCreditApply, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot apply credit to void invoice")
    if not invoice.customer_id:
        raise HTTPException(status_code=400, detail="Invoice has no customer for credit application")

    credits = (await db.execute(select(CustomerCredit).where(CustomerCredit.customer_id == invoice.customer_id).order_by(CustomerCredit.credit_date.asc(), CustomerCredit.created_at.asc()))).scalars().all()
    remaining_to_apply = body.amount
    for credit in credits:
        if remaining_to_apply <= 0:
            break
        if credit.remaining_amount <= 0:
            continue
        apply_amt = min(credit.remaining_amount, remaining_to_apply)
        credit.remaining_amount = credit.remaining_amount - apply_amt
        remaining_to_apply -= apply_amt
        invoice.credits_applied = invoice.credits_applied + apply_amt

    if remaining_to_apply > 0:
        raise HTTPException(status_code=400, detail="Insufficient remaining customer credit")

    _recalculate_invoice(invoice)
    await db.commit()
    return await _get_invoice(db, invoice.id)


@router.get("/reports/ar-aging", response_model=ARAgingSummary, summary="A/R aging report")
async def ar_aging_report(db: DB, as_of_date: datetime.date | None = Query(None)):
    as_of = as_of_date or datetime.date.today()
    result = await db.execute(select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.is_deleted == False))
    invoices = result.scalars().all()
    rows: list[ARAgingRow] = []
    totals = {"current": Decimal("0"), "bucket_1_30": Decimal("0"), "bucket_31_60": Decimal("0"), "bucket_61_90": Decimal("0"), "bucket_90_plus": Decimal("0")}

    for invoice in invoices:
        invoice.status = _derive_invoice_status(invoice, as_of)
        if invoice.balance_due <= 0 or invoice.status == "void":
            continue
        due_date = invoice.due_date or invoice.issue_date
        age_days = max((as_of - due_date).days, 0)
        current = bucket_1_30 = bucket_31_60 = bucket_61_90 = bucket_90_plus = Decimal("0")
        if invoice.due_date and as_of <= invoice.due_date:
            current = invoice.balance_due
            totals["current"] += invoice.balance_due
        elif age_days <= 30:
            bucket_1_30 = invoice.balance_due
            totals["bucket_1_30"] += invoice.balance_due
        elif age_days <= 60:
            bucket_31_60 = invoice.balance_due
            totals["bucket_31_60"] += invoice.balance_due
        elif age_days <= 90:
            bucket_61_90 = invoice.balance_due
            totals["bucket_61_90"] += invoice.balance_due
        else:
            bucket_90_plus = invoice.balance_due
            totals["bucket_90_plus"] += invoice.balance_due
        rows.append(ARAgingRow(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer_name,
            due_date=invoice.due_date,
            balance_due=invoice.balance_due,
            current=current,
            bucket_1_30=bucket_1_30,
            bucket_31_60=bucket_31_60,
            bucket_61_90=bucket_61_90,
            bucket_90_plus=bucket_90_plus,
        ))

    return ARAgingSummary(
        as_of_date=as_of,
        rows=rows,
        current_total=totals["current"],
        bucket_1_30_total=totals["bucket_1_30"],
        bucket_31_60_total=totals["bucket_31_60"],
        bucket_61_90_total=totals["bucket_61_90"],
        bucket_90_plus_total=totals["bucket_90_plus"],
        total_outstanding=sum(totals.values(), Decimal("0")),
    )


@router.delete("/{invoice_id}", status_code=204, summary="Delete invoice")
async def delete_invoice(invoice_id: uuid.UUID, user: CurrentUser, db: DB):
    invoice = await _get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.is_deleted = True
    await db.commit()
