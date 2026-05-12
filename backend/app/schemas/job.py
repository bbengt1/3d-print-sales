from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.plate import PlateIn, PlateResponse
from app.schemas.printer import PrinterResponse


class JobStatus(str, Enum):
    draft = "draft"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


_UNIFORM_FIELDS = ("qty_per_plate", "num_plates", "material_per_plate_g", "print_time_per_plate_hrs")


class JobCreate(BaseModel):
    job_number: str | None = Field(None, min_length=1, max_length=50, examples=["2026.03.04.001"])
    date: datetime.date = Field(..., examples=["2026-03-04"])
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200, examples=["Sample Customer"])
    product_name: str = Field(..., min_length=1, max_length=200, examples=["Phone Stand"])
    qty_per_plate: int | None = Field(None, gt=0, examples=[1])
    num_plates: int | None = Field(None, gt=0, examples=[1])
    material_id: uuid.UUID
    material_per_plate_g: Decimal | None = Field(None, gt=0, examples=[45.0])
    print_time_per_plate_hrs: Decimal | None = Field(None, gt=0, examples=[2.5])
    labor_mins: Decimal = Field(Decimal(0), ge=0, examples=[15])
    design_time_hrs: Decimal | None = Field(Decimal(0), ge=0, examples=[0.5])
    shipping_cost: Decimal = Field(Decimal(0), ge=0, examples=[0])
    target_margin_pct: Decimal = Field(Decimal(40), ge=0, le=99, examples=[40])
    product_id: uuid.UUID | None = None
    printer_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    status: JobStatus = Field(JobStatus.completed, examples=["completed"])
    plates: list[PlateIn] | None = Field(None, description="Per-plate breakdown for multi-part prints. If provided, supersedes uniform fields.")

    @model_validator(mode="after")
    def _validate_mode(self) -> "JobCreate":
        if self.plates:
            if not self.plates:
                raise ValueError("plates must contain at least one entry")
        else:
            missing = [f for f in _UNIFORM_FIELDS if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Either 'plates' or all uniform fields must be provided. Missing: {missing}")
        return self


class JobUpdate(BaseModel):
    job_number: str | None = Field(None, min_length=1, max_length=50)
    date: datetime.date | None = None
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
    product_id: uuid.UUID | None = None
    printer_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    status: JobStatus | None = None
    plates: list[PlateIn] | None = None


class CalculateRequest(BaseModel):
    qty_per_plate: int = Field(..., gt=0, examples=[1])
    num_plates: int = Field(..., gt=0, examples=[1])
    material_id: uuid.UUID
    material_per_plate_g: Decimal = Field(..., gt=0, examples=[45.0])
    print_time_per_plate_hrs: Decimal = Field(..., gt=0, examples=[2.5])
    labor_mins: Decimal = Field(Decimal(0), ge=0, examples=[15])
    design_time_hrs: Decimal | None = Field(Decimal(0), ge=0, examples=[0.5])
    shipping_cost: Decimal = Field(Decimal(0), ge=0, examples=[0])
    target_margin_pct: Decimal = Field(Decimal(40), ge=0, le=99, examples=[40])


class CalculateResponse(BaseModel):
    total_pieces: int
    electricity_cost: float
    material_cost: float
    labor_cost: float
    design_cost: float
    machine_cost: float
    packaging_cost: float
    shipping_cost: float
    failure_buffer: float
    subtotal_cost: float
    overhead: float
    total_cost: float
    cost_per_piece: float
    price_per_piece: float
    total_revenue: float
    platform_fees: float
    net_profit: float
    profit_per_piece: float


class JobResponse(BaseModel):
    id: uuid.UUID
    job_number: str
    date: datetime.date
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    product_name: str
    qty_per_plate: int | None = None
    num_plates: int | None = None
    material_id: uuid.UUID
    total_pieces: int
    material_per_plate_g: Decimal | None = None
    print_time_per_plate_hrs: Decimal | None = None
    total_material_g: Decimal
    total_print_time_hrs: Decimal
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
    product_id: uuid.UUID | None = None
    printer_id: uuid.UUID | None = None
    printer: PrinterResponse | None = None
    project_id: uuid.UUID | None = None
    inventory_added: bool = False
    status: str
    plates: list[PlateResponse] = []
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedJobs(BaseModel):
    items: list[JobResponse]
    total: int
    skip: int
    limit: int
