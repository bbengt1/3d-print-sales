from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Labor rate"])
    value: Decimal = Field(..., ge=0, examples=[25.00])
    unit: str = Field(..., min_length=1, max_length=20, examples=["$/hour"])
    notes: str | None = Field(None, max_length=500, examples=["Hands-on + design time"])
    active: bool = Field(True)


class RateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    value: Decimal | None = Field(None, ge=0)
    unit: str | None = Field(None, min_length=1, max_length=20)
    notes: str | None = Field(None, max_length=500)
    active: bool | None = None


class RateResponse(BaseModel):
    id: uuid.UUID
    name: str
    value: Decimal
    unit: str
    notes: str | None = None
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
