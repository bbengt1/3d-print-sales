from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.billable_expense import BillableExpense
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine


router = APIRouter(prefix="/billable-expenses", tags=["BillableExpenses"])


class BillableExpenseCreate(BaseModel):
    customer_id: uuid.UUID
    bill_id: uuid.UUID | None = None
    description: str = Field(..., min_length=1, max_length=255)
    cost: Decimal = Field(..., gt=0)
    markup_pct: Decimal = Field(0, ge=0)
    incurred_on: datetime.date
    notes: str | None = None


class BillableExpenseUpdate(BaseModel):
    description: str | None = Field(None, max_length=255)
    cost: Decimal | None = Field(None, gt=0)
    markup_pct: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class BillableExpenseResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    bill_id: uuid.UUID | None
    description: str
    cost: Decimal
    markup_pct: Decimal
    incurred_on: datetime.date
    status: str
    invoice_id: uuid.UUID | None
    notes: str | None
    rebillable_amount: Decimal


def _rebill_amt(b: BillableExpense) -> Decimal:
    return (Decimal(b.cost) * (Decimal("1") + Decimal(b.markup_pct) / Decimal("100"))).quantize(Decimal("0.01"))


def _to_resp(b: BillableExpense) -> BillableExpenseResponse:
    return BillableExpenseResponse(
        id=b.id, customer_id=b.customer_id, bill_id=b.bill_id,
        description=b.description, cost=Decimal(b.cost),
        markup_pct=Decimal(b.markup_pct), incurred_on=b.incurred_on,
        status=b.status, invoice_id=b.invoice_id, notes=b.notes,
        rebillable_amount=_rebill_amt(b),
    )


@router.get("", response_model=list[BillableExpenseResponse], summary="List billable expenses")
async def list_be(
    user: CurrentUser,
    db: DB,
    customer_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    stmt = select(BillableExpense).order_by(BillableExpense.incurred_on.desc())
    if customer_id is not None:
        stmt = stmt.where(BillableExpense.customer_id == customer_id)
    if status_filter:
        stmt = stmt.where(BillableExpense.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_resp(b) for b in rows]


@router.post("", response_model=BillableExpenseResponse, status_code=status.HTTP_201_CREATED, summary="Mark an expense as billable")
async def create_be(body: BillableExpenseCreate, user: CurrentUser, db: DB):
    b = BillableExpense(**body.model_dump())
    db.add(b)
    await db.commit()
    return _to_resp(b)


@router.patch("/{be_id}", response_model=BillableExpenseResponse, summary="Update a pending billable expense")
async def update_be(be_id: uuid.UUID, body: BillableExpenseUpdate, user: CurrentUser, db: DB):
    b = (await db.execute(select(BillableExpense).where(BillableExpense.id == be_id))).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Billable expense not found")
    if b.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot edit billable expense in status {b.status}")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    await db.commit()
    return _to_resp(b)


@router.post("/{be_id}/void", response_model=BillableExpenseResponse, summary="Void a pending billable expense")
async def void_be(be_id: uuid.UUID, user: CurrentUser, db: DB):
    b = (await db.execute(select(BillableExpense).where(BillableExpense.id == be_id))).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Billable expense not found")
    if b.status == "invoiced":
        raise HTTPException(status_code=400, detail="Cannot void an invoiced billable expense")
    b.status = "voided"
    await db.commit()
    return _to_resp(b)


class AddToInvoiceRequest(BaseModel):
    invoice_id: uuid.UUID


@router.post(
    "/{be_id}/add-to-invoice",
    response_model=BillableExpenseResponse,
    summary="#263 P2: Append the rebillable amount as a pass-through line on an invoice",
)
async def add_to_invoice(be_id: uuid.UUID, body: AddToInvoiceRequest, user: CurrentUser, db: DB):
    b = (await db.execute(select(BillableExpense).where(BillableExpense.id == be_id))).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Billable expense not found")
    if b.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot rebill in status {b.status}")
    inv = (
        await db.execute(select(Invoice).where(Invoice.id == body.invoice_id, Invoice.is_deleted == False))  # noqa: E712
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.customer_id is not None and inv.customer_id != b.customer_id:
        raise HTTPException(status_code=400, detail="Invoice belongs to a different customer")

    rebill = _rebill_amt(b)
    db.add(
        InvoiceLine(
            invoice_id=inv.id,
            description=f"Pass-through: {b.description}",
            quantity=1,
            unit_price=rebill,
            line_total=rebill,
            notes=f"From billable expense {b.id}",
        )
    )
    inv.subtotal = Decimal(inv.subtotal) + rebill
    inv.total_due = Decimal(inv.total_due) + rebill
    inv.balance_due = Decimal(inv.balance_due) + rebill
    b.status = "invoiced"
    b.invoice_id = inv.id
    await db.commit()
    return _to_resp(b)
