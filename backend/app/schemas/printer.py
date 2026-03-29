from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PrinterStatus(str, Enum):
    idle = "idle"
    printing = "printing"
    paused = "paused"
    maintenance = "maintenance"
    offline = "offline"
    error = "error"


class PrinterMonitorProvider(str, Enum):
    octoprint = "octoprint"
    moonraker = "moonraker"


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
    monitor_enabled: bool = False
    monitor_provider: PrinterMonitorProvider | None = None
    monitor_base_url: str | None = Field(None, max_length=500)
    monitor_api_key: str | None = Field(None, max_length=255)
    monitor_poll_interval_seconds: int = Field(30, ge=5, le=3600)

    @field_validator("monitor_base_url")
    @classmethod
    def normalize_monitor_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value.rstrip("/") or None


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
    monitor_enabled: bool | None = None
    monitor_provider: PrinterMonitorProvider | None = None
    monitor_base_url: str | None = Field(None, max_length=500)
    monitor_api_key: str | None = Field(None, max_length=255)
    monitor_poll_interval_seconds: int | None = Field(None, ge=5, le=3600)

    @field_validator("monitor_base_url")
    @classmethod
    def normalize_monitor_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value.rstrip("/") or None


class PrinterThumbnailResponse(BaseModel):
    relative_path: str
    width: int | None = None
    height: int | None = None
    size: int | None = None


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
    monitor_enabled: bool
    monitor_provider: str | None = None
    monitor_base_url: str | None = None
    monitor_api_key: str | None = None
    monitor_poll_interval_seconds: int
    monitor_online: bool | None = None
    monitor_status: str | None = None
    monitor_progress_percent: float | None = None
    current_print_name: str | None = None
    monitor_last_message: str | None = None
    monitor_last_error: str | None = None
    current_print_thumbnail_path: str | None = None
    current_print_thumbnail_url: str | None = None
    current_print_thumbnails: list[PrinterThumbnailResponse] = Field(default_factory=list)
    monitor_bed_temp_c: float | None = None
    monitor_tool_temp_c: float | None = None
    monitor_bed_target_c: float | None = None
    monitor_tool_target_c: float | None = None
    monitor_current_layer: int | None = None
    monitor_total_layers: int | None = None
    monitor_elapsed_seconds: float | None = None
    monitor_remaining_seconds: float | None = None
    monitor_eta_at: datetime | None = None
    monitor_last_event_type: str | None = None
    monitor_last_event_at: datetime | None = None
    monitor_ws_connected: bool | None = None
    monitor_ws_last_error: str | None = None
    monitor_last_seen_at: datetime | None = None
    monitor_last_updated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PrinterConnectionTestResponse(BaseModel):
    ok: bool
    provider: str
    normalized_status: str | None = None
    online: bool | None = None
    message: str | None = None


class PaginatedPrinters(BaseModel):
    items: list[PrinterResponse]
    total: int
    skip: int
    limit: int
