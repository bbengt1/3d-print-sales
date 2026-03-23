from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class QuoteStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class QuoteBase(BaseModel):
    date: datetime.date
    valid_until: datetime.date | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200)
    product_name: str = Field(..., min_length=1, max_length=200)
    qty_per_plate: int = Field(..., gt=0)
    num_plates: int = Field(..., gt=0)
    material_id: uuid.UUID
    material_per_plate_g: Decimal = Field(..., gt=0)
    print_time_per_plate_hrs: Decimal = Field(..., gt=0)
    labor_mins: Decimal = Field(Decimal(0), ge=0)
    design_time_hrs: Decimal | None = Field(Decimal(0), ge=0)
    shipping_cost: Decimal = Field(Decimal(0), ge=0)
    target_margin_pct: Decimal = Field(Decimal(40), ge=0, le=99)
    notes: str | None = None


class QuoteCreate(QuoteBase):
    quote_number: str = Field(..., min_length=1, max_length=50)
    status: QuoteStatus = QuoteStatus.draft


class QuoteUpdate(BaseModel):
    valid_until: datetime.date | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200)
    product_name: str | None = Field(None, min_length=1, max_length=200)
    qty_per_plate: int | None = Field(None, gt=0)
    num_plates: int | None = Field(None, gt=0)
    material_id: uuid.UUID | None = None
    material_per_plate_g: Decimal | None = Field(None, gt=0)
    print_time_per_plate_hrs: Decimal | None = Field(None, gt=0)
    labor_mins: Decimal | None = Field(None, ge=0)
    design_time_hrs: Decimal | None = Field(None, ge=0)
    shipping_cost: Decimal | None = Field(None, ge=0)
    target_margin_pct: Decimal | None = Field(None, ge=0, le=99)
    notes: str | None = None
    status: QuoteStatus | None = None


class QuoteConvertToJob(BaseModel):
    job_number: str = Field(..., min_length=1, max_length=50)
    job_date: datetime.date | None = None
    status: str = Field("draft", pattern="^(draft|in_progress|completed|cancelled)$")


class QuoteResponse(BaseModel):
    id: uuid.UUID
    quote_number: str
    date: datetime.date
    valid_until: datetime.date | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    product_name: str
    qty_per_plate: int
    num_plates: int
    material_id: uuid.UUID
    total_pieces: int
    material_per_plate_g: Decimal
    print_time_per_plate_hrs: Decimal
    labor_mins: Decimal
    design_time_hrs: Decimal | None = None
    electricity_cost: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    design_cost: Decimal
    machine_cost: Decimal
    packaging_cost: Decimal
    shipping_cost: Decimal
    failure_buffer: Decimal
    subtotal_cost: Decimal
    overhead: Decimal
    total_cost: Decimal
    cost_per_piece: Decimal
    target_margin_pct: Decimal
    price_per_piece: Decimal
    total_revenue: Decimal
    platform_fees: Decimal
    net_profit: Decimal
    profit_per_piece: Decimal
    job_id: uuid.UUID | None = None
    notes: str | None = None
    status: str
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedQuotes(BaseModel):
    items: list[QuoteResponse]
    total: int
    skip: int
    limit: int
