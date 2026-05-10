from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, examples=["John Doe"])
    email: EmailStr | None = Field(None, examples=["john@example.com"])
    phone: str | None = Field(None, max_length=50, examples=["555-0100"])
    notes: str | None = Field(None, max_length=1000)
    # #263 P2: per-customer late-fee terms (NULL → fall back to global setting)
    late_payment_fee_rate_pct: Decimal | None = Field(None, ge=0)
    late_payment_fee_grace_days: int | None = Field(None, ge=0)


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=1000)
    late_payment_fee_rate_pct: Decimal | None = Field(None, ge=0)
    late_payment_fee_grace_days: int | None = Field(None, ge=0)


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    late_payment_fee_rate_pct: Decimal | None = None
    late_payment_fee_grace_days: int | None = None
    job_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
