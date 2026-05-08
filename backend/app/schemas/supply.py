from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SupplyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, examples=["10x3mm magnet"])
    sku: str | None = Field(None, max_length=100, examples=["MAG-10X3"])
    category: str | None = Field(None, max_length=80, examples=["hardware"])
    unit: str = Field("each", min_length=1, max_length=20, examples=["each"])
    unit_cost: Decimal = Field(Decimal(0), ge=0, examples=[Decimal("0.18")])
    quantity_on_hand: Decimal = Field(Decimal(0), ge=0, examples=[Decimal("200")])
    reorder_point: Decimal = Field(Decimal(0), ge=0, examples=[Decimal("25")])
    supplier: str | None = Field(None, max_length=200, examples=["AliExpress"])
    supplier_url: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=500)
    active: bool = Field(True)


class SupplyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    sku: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=80)
    unit: str | None = Field(None, min_length=1, max_length=20)
    unit_cost: Decimal | None = Field(None, ge=0)
    quantity_on_hand: Decimal | None = Field(None, ge=0)
    reorder_point: Decimal | None = Field(None, ge=0)
    supplier: str | None = Field(None, max_length=200)
    supplier_url: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=500)
    active: bool | None = None


class SupplyAdjust(BaseModel):
    quantity_delta: Decimal = Field(..., examples=[Decimal("25")])
    notes: str | None = Field(None, max_length=500)


class SupplyResponse(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None = None
    category: str | None = None
    unit: str
    unit_cost: Decimal
    quantity_on_hand: Decimal
    reorder_point: Decimal
    supplier: str | None = None
    supplier_url: str | None = None
    notes: str | None = None
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
