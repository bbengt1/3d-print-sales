from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class AccountBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=120)
    account_type: str = Field(..., pattern="^(asset|liability|equity|revenue|cogs|expense)$")
    normal_balance: str = Field(..., pattern="^(debit|credit)$")
    parent_id: uuid.UUID | None = None
    description: str | None = None
    is_active: bool = True


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    account_type: str | None = Field(None, pattern="^(asset|liability|equity|revenue|cogs|expense)$")
    normal_balance: str | None = Field(None, pattern="^(debit|credit)$")
    parent_id: uuid.UUID | None = None
    description: str | None = None
    is_active: bool | None = None


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


class AccountingPeriodBase(BaseModel):
    period_key: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    start_date: datetime.date
    end_date: datetime.date
    status: str = Field("open", pattern="^(open|closed|locked)$")
    is_adjustment_period: bool = False


class AccountingPeriodCreate(AccountingPeriodBase):
    pass


class AccountingPeriodUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    status: str | None = Field(None, pattern="^(open|closed|locked)$")
    is_adjustment_period: bool | None = None


class AccountingPeriodStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|closed|locked)$")


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


class JournalEntryReverse(BaseModel):
    reversal_date: datetime.date
    memo: str | None = None


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
    reversal_of_id: uuid.UUID | None = None
    lines: list[JournalLineResponse] = []
