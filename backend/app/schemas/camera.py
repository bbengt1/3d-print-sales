from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=120)
    go2rtc_base_url: str = Field(..., min_length=1, max_length=500)
    stream_name: str = Field(..., min_length=1, max_length=120)
    printer_id: uuid.UUID | None = None
    is_active: bool = True
    notes: str | None = Field(None, max_length=1000)

    @field_validator("go2rtc_base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value.rstrip("/") or None


class CameraUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    slug: str | None = Field(None, min_length=1, max_length=120)
    go2rtc_base_url: str | None = Field(None, min_length=1, max_length=500)
    stream_name: str | None = Field(None, min_length=1, max_length=120)
    printer_id: uuid.UUID | None = None
    clear_printer_id: bool = False
    is_active: bool | None = None
    notes: str | None = Field(None, max_length=1000)

    @field_validator("go2rtc_base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value.rstrip("/") or None


class CameraResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    go2rtc_base_url: str
    stream_name: str
    printer_id: uuid.UUID | None = None
    printer_name: str | None = None
    is_active: bool
    notes: str | None = None
    snapshot_url: str | None = None
    mse_ws_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedCameras(BaseModel):
    items: list[CameraResponse]
    total: int
    skip: int
    limit: int
