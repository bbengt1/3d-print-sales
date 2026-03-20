from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Etsy"])
    platform_fee_pct: Decimal = Field(Decimal(0), ge=0, le=100, examples=[9.5])
    fixed_fee: Decimal = Field(Decimal(0), ge=0, examples=[0.45])
    is_active: bool = Field(True)


class SalesChannelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    platform_fee_pct: Decimal | None = Field(None, ge=0, le=100)
    fixed_fee: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None


class SalesChannelResponse(BaseModel):
    id: uuid.UUID
    name: str
    platform_fee_pct: Decimal
    fixed_fee: Decimal
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
