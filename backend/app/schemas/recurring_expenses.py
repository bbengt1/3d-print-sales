from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RecurringExpenseCreate(BaseModel):
    vendor_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    account_id: uuid.UUID
    description: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0)
    tax_amount: Decimal = Field(0, ge=0)
    frequency: str = Field("monthly", pattern="^(weekly|monthly|quarterly|yearly)$")
    next_due_date: datetime.date
    payment_method: str | None = Field(None, max_length=50)
    notes: str | None = None
    is_active: bool = True


class RecurringExpenseUpdate(BaseModel):
    vendor_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    description: str | None = Field(None, min_length=1, max_length=255)
    amount: Decimal | None = Field(None, gt=0)
    tax_amount: Decimal | None = Field(None, ge=0)
    frequency: str | None = Field(None, pattern="^(weekly|monthly|quarterly|yearly)$")
    next_due_date: datetime.date | None = None
    payment_method: str | None = Field(None, max_length=50)
    notes: str | None = None
    is_active: bool | None = None


class RecurringExpenseGenerate(BaseModel):
    as_of_date: datetime.date


class RecurringExpenseResponse(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    account_id: uuid.UUID
    description: str
    amount: Decimal
    tax_amount: Decimal
    frequency: str
    next_due_date: datetime.date
    payment_method: str | None = None
    notes: str | None = None
    is_active: bool
    last_generated_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseSummaryRow(BaseModel):
    key: str
    label: str
    total_amount: Decimal
    bill_count: int
