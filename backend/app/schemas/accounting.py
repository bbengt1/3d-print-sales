from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    account_type: str
    normal_balance: str
    parent_id: uuid.UUID | None = None
    description: str | None = None
    is_active: bool
    is_system: bool
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


class AccountingPeriodResponse(BaseModel):
    id: uuid.UUID
    period_key: str
    name: str
    start_date: datetime.date
    end_date: datetime.date
    status: str
    is_adjustment_period: bool
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


class JournalLineCreate(BaseModel):
    account_id: uuid.UUID
    entry_type: str = Field(..., pattern="^(debit|credit)$")
    amount: Decimal = Field(..., gt=0)
    description: str | None = None


class JournalEntryCreate(BaseModel):
    entry_date: datetime.date
    accounting_period_id: uuid.UUID | None = None
    source_type: str | None = None
    source_id: str | None = None
    memo: str | None = None
    lines: list[JournalLineCreate]


class JournalLineResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    line_number: int
    entry_type: str
    amount: Decimal
    description: str | None = None


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    entry_number: str
    entry_date: datetime.date
    accounting_period_id: uuid.UUID | None = None
    status: str
    source_type: str | None = None
    source_id: str | None = None
    memo: str | None = None
    posted_at: datetime.datetime | None = None
    is_reversal: bool
    lines: list[JournalLineResponse] = []
