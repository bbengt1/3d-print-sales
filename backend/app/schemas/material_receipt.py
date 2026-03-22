from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class MaterialReceiptCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=120)
    purchase_date: datetime.date
    receipt_number: str | None = Field(None, max_length=60)
    quantity_purchased_g: Decimal = Field(..., gt=0)
    unit_cost_per_g: Decimal = Field(..., gt=0)
    landed_cost_total: Decimal = Field(0, ge=0)
    valuation_method: str = Field("lot", pattern="^(lot|average)$")
    notes: str | None = Field(None, max_length=500)


class MaterialReceiptResponse(BaseModel):
    id: uuid.UUID
    material_id: uuid.UUID
    vendor_name: str
    purchase_date: datetime.date
    receipt_number: str | None = None
    quantity_purchased_g: Decimal
    quantity_remaining_g: Decimal
    unit_cost_per_g: Decimal
    landed_cost_total: Decimal
    landed_cost_per_g: Decimal
    total_cost: Decimal
    valuation_method: str
    notes: str | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None

    model_config = {"from_attributes": True}
