from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    payment_date: datetime.date
    amount: Decimal = Field(..., gt=0)
    payment_method: str | None = Field(None, max_length=50)
    reference_number: str | None = Field(None, max_length=60)
    notes: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    payment_date: datetime.date
    amount: Decimal
    payment_method: str | None = None
    reference_number: str | None = None
    notes: str | None = None
    unapplied_amount: Decimal
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerCreditCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    credit_date: datetime.date
    amount: Decimal = Field(..., gt=0)
    reason: str | None = Field(None, max_length=120)
    notes: str | None = None


class CustomerCreditApply(BaseModel):
    amount: Decimal = Field(..., gt=0)


class CustomerCreditResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    credit_date: datetime.date
    amount: Decimal
    remaining_amount: Decimal
    reason: str | None = None
    notes: str | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ARAgingRow(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    due_date: datetime.date | None = None
    balance_due: Decimal
    current: Decimal
    bucket_1_30: Decimal
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_90_plus: Decimal


class ARAgingSummary(BaseModel):
    as_of_date: datetime.date
    rows: list[ARAgingRow]
    current_total: Decimal
    bucket_1_30_total: Decimal
    bucket_31_60_total: Decimal
    bucket_61_90_total: Decimal
    bucket_90_plus_total: Decimal
    total_outstanding: Decimal
