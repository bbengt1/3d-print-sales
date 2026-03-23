from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InvoiceStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    partially_paid = "partially_paid"
    paid = "paid"
    overdue = "overdue"
    void = "void"


class InvoiceLineCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    notes: str | None = None


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    notes: str | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(..., min_length=1, max_length=50)
    quote_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200)
    issue_date: datetime.date
    due_date: datetime.date | None = None
    tax_amount: Decimal = Field(0, ge=0)
    shipping_amount: Decimal = Field(0, ge=0)
    credits_applied: Decimal = Field(0, ge=0)
    notes: str | None = None
    status: InvoiceStatus = InvoiceStatus.draft
    lines: list[InvoiceLineCreate] = Field(default_factory=list, min_length=1)


class InvoiceUpdate(BaseModel):
    due_date: datetime.date | None = None
    tax_amount: Decimal | None = Field(None, ge=0)
    shipping_amount: Decimal | None = Field(None, ge=0)
    credits_applied: Decimal | None = Field(None, ge=0)
    notes: str | None = None
    status: InvoiceStatus | None = None


class InvoicePaymentApply(BaseModel):
    amount: Decimal = Field(..., gt=0)
    paid_at: datetime.date | None = None


class InvoiceCreditApply(BaseModel):
    amount: Decimal = Field(..., gt=0)


class InvoiceFromQuoteCreate(BaseModel):
    invoice_number: str = Field(..., min_length=1, max_length=50)
    issue_date: datetime.date
    due_date: datetime.date | None = None
    tax_amount: Decimal = Field(0, ge=0)
    shipping_amount: Decimal | None = Field(None, ge=0)
    credits_applied: Decimal = Field(0, ge=0)
    notes: str | None = None
    status: InvoiceStatus = InvoiceStatus.draft


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    quote_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    issue_date: datetime.date
    due_date: datetime.date | None = None
    subtotal: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    credits_applied: Decimal
    total_due: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    status: str
    notes: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    lines: list[InvoiceLineResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedInvoices(BaseModel):
    items: list[InvoiceResponse]
    total: int
    skip: int
    limit: int
