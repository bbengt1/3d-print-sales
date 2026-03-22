from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BillCreate(BaseModel):
    vendor_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    account_id: uuid.UUID
    bill_number: str | None = Field(None, max_length=60)
    description: str = Field(..., min_length=1, max_length=255)
    issue_date: datetime.date
    due_date: datetime.date | None = None
    amount: Decimal = Field(..., gt=0)
    tax_amount: Decimal = Field(0, ge=0)
    payment_method: str | None = Field(None, max_length=50)
    notes: str | None = None


class BillUpdate(BaseModel):
    vendor_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    bill_number: str | None = Field(None, max_length=60)
    description: str | None = Field(None, min_length=1, max_length=255)
    issue_date: datetime.date | None = None
    due_date: datetime.date | None = None
    amount: Decimal | None = Field(None, gt=0)
    tax_amount: Decimal | None = Field(None, ge=0)
    payment_method: str | None = Field(None, max_length=50)
    notes: str | None = None
    status: str | None = Field(None, pattern="^(draft|open|partially_paid|paid|void)$")


class BillPaymentCreate(BaseModel):
    payment_date: datetime.date
    amount: Decimal = Field(..., gt=0)
    payment_method: str | None = Field(None, max_length=50)
    reference_number: str | None = Field(None, max_length=60)
    notes: str | None = None


class BillPaymentResponse(BaseModel):
    id: uuid.UUID
    bill_id: uuid.UUID
    payment_date: datetime.date
    amount: Decimal
    payment_method: str | None = None
    reference_number: str | None = None
    notes: str | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BillResponse(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    account_id: uuid.UUID
    bill_number: str | None = None
    description: str
    issue_date: datetime.date
    due_date: datetime.date | None = None
    amount: Decimal
    tax_amount: Decimal
    amount_paid: Decimal
    status: str
    payment_method: str | None = None
    notes: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    payments: list[BillPaymentResponse] = []

    model_config = ConfigDict(from_attributes=True)
