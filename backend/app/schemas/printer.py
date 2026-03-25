from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PrinterStatus(str, Enum):
    idle = "idle"
    printing = "printing"
    paused = "paused"
    maintenance = "maintenance"
    offline = "offline"
    error = "error"


class PrinterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=120)
    manufacturer: str | None = Field(None, max_length=120)
    model: str | None = Field(None, max_length=120)
    serial_number: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    status: PrinterStatus = PrinterStatus.idle
    is_active: bool = True
    notes: str | None = Field(None, max_length=1000)


class PrinterUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    slug: str | None = Field(None, min_length=1, max_length=120)
    manufacturer: str | None = Field(None, max_length=120)
    model: str | None = Field(None, max_length=120)
    serial_number: str | None = Field(None, max_length=120)
    location: str | None = Field(None, max_length=120)
    status: PrinterStatus | None = None
    is_active: bool | None = None
    notes: str | None = Field(None, max_length=1000)


class PrinterResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    location: str | None = None
    status: str
    is_active: bool
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedPrinters(BaseModel):
    items: list[PrinterResponse]
    total: int
    skip: int
    limit: int
