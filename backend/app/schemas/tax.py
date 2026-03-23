from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TaxProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    jurisdiction: str = Field(..., min_length=1, max_length=120)
    tax_rate: Decimal = Field(0, ge=0)
    filing_frequency: str | None = Field(None, max_length=20)
    is_marketplace_facilitated: bool = False
    is_active: bool = True
    notes: str | None = None


class TaxProfileUpdate(BaseModel):
    jurisdiction: str | None = Field(None, min_length=1, max_length=120)
    tax_rate: Decimal | None = Field(None, ge=0)
    filing_frequency: str | None = Field(None, max_length=20)
    is_marketplace_facilitated: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class TaxProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    jurisdiction: str
    tax_rate: Decimal
    filing_frequency: str | None = None
    is_marketplace_facilitated: bool
    is_active: bool
    notes: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TaxRemittanceCreate(BaseModel):
    tax_profile_id: uuid.UUID
    period_start: datetime.date
    period_end: datetime.date
    remittance_date: datetime.date
    amount: Decimal = Field(..., gt=0)
    reference_number: str | None = Field(None, max_length=60)
    notes: str | None = None


class TaxRemittanceResponse(BaseModel):
    id: uuid.UUID
    tax_profile_id: uuid.UUID
    period_start: datetime.date
    period_end: datetime.date
    remittance_date: datetime.date
    amount: Decimal
    reference_number: str | None = None
    notes: str | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TaxLiabilityRow(BaseModel):
    tax_profile_id: uuid.UUID
    tax_profile_name: str
    jurisdiction: str
    seller_collected: Decimal
    marketplace_facilitated: Decimal
    remitted: Decimal
    outstanding_liability: Decimal


class TaxLiabilitySummary(BaseModel):
    date_from: datetime.date | None = None
    date_to: datetime.date | None = None
    rows: list[TaxLiabilityRow]
    total_seller_collected: Decimal
    total_marketplace_facilitated: Decimal
    total_remitted: Decimal
    total_outstanding_liability: Decimal
