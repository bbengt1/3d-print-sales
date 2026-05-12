from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class PlateIn(BaseModel):
    plate_number: int | None = Field(None, gt=0, examples=[1])
    printer_id: uuid.UUID | None = None
    parts_count: int = Field(..., gt=0, examples=[4])
    material_g: Decimal = Field(..., gt=0, examples=[45.0])
    print_time_hrs: Decimal = Field(..., gt=0, examples=[2.5])


class PlateResponse(BaseModel):
    id: uuid.UUID
    plate_number: int
    printer_id: uuid.UUID | None = None
    parts_count: int
    material_g: Decimal
    print_time_hrs: Decimal

    model_config = {"from_attributes": True}
