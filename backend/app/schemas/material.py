from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, examples=["PLA"])
    brand: str = Field(..., min_length=1, max_length=100, examples=["Generic"])
    spool_weight_g: Decimal = Field(..., gt=0, examples=[1000])
    spool_price: Decimal = Field(..., gt=0, examples=[20.00])
    net_usable_g: Decimal = Field(..., gt=0, examples=[950])
    notes: str | None = Field(None, max_length=500, examples=["Standard PLA spool"])
    active: bool = Field(True)


class MaterialUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    brand: str | None = Field(None, min_length=1, max_length=100)
    spool_weight_g: Decimal | None = Field(None, gt=0)
    spool_price: Decimal | None = Field(None, gt=0)
    net_usable_g: Decimal | None = Field(None, gt=0)
    notes: str | None = Field(None, max_length=500)
    active: bool | None = None


class MaterialResponse(BaseModel):
    id: uuid.UUID
    name: str
    brand: str
    spool_weight_g: Decimal
    spool_price: Decimal
    net_usable_g: Decimal
    cost_per_g: Decimal
    notes: str | None = None
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
