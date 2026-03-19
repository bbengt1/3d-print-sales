from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models.job import Job
from app.services.cost_calculator import CostCalculator

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobCreate(BaseModel):
    job_number: str
    date: datetime.date
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    product_name: str
    qty_per_plate: int
    num_plates: int
    material_id: uuid.UUID
    material_per_plate_g: Decimal
    print_time_per_plate_hrs: Decimal
    labor_mins: Decimal = Decimal(0)
    design_time_hrs: Decimal | None = Decimal(0)
    shipping_cost: Decimal = Decimal(0)
    target_margin_pct: Decimal = Decimal(40)
    status: str = "completed"


class JobUpdate(BaseModel):
    job_number: str | None = None
    date: datetime.date | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    product_name: str | None = None
    qty_per_plate: int | None = None
    num_plates: int | None = None
    material_id: uuid.UUID | None = None
    material_per_plate_g: Decimal | None = None
    print_time_per_plate_hrs: Decimal | None = None
    labor_mins: Decimal | None = None
    design_time_hrs: Decimal | None = None
    shipping_cost: Decimal | None = None
    target_margin_pct: Decimal | None = None
    status: str | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    job_number: str
    date: datetime.date
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    product_name: str
    qty_per_plate: int
    num_plates: int
    material_id: uuid.UUID
    total_pieces: int
    material_per_plate_g: Decimal
    print_time_per_plate_hrs: Decimal
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
    status: str

    model_config = {"from_attributes": True}


class CalculateRequest(BaseModel):
    qty_per_plate: int
    num_plates: int
    material_id: uuid.UUID
    material_per_plate_g: Decimal
    print_time_per_plate_hrs: Decimal
    labor_mins: Decimal = Decimal(0)
    design_time_hrs: Decimal | None = Decimal(0)
    shipping_cost: Decimal = Decimal(0)
    target_margin_pct: Decimal = Decimal(40)


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    db: DB,
    status: str | None = Query(None),
    material_id: uuid.UUID | None = Query(None),
    skip: int = 0,
    limit: int = 50,
):
    stmt = select(Job).where(Job.is_deleted == False)
    if status:
        stmt = stmt.where(Job.status == status)
    if material_id:
        stmt = stmt.where(Job.material_id == material_id)
    stmt = stmt.order_by(Job.date.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: DB):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, db: DB):
    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=body.material_id,
        qty_per_plate=body.qty_per_plate,
        num_plates=body.num_plates,
        material_per_plate_g=body.material_per_plate_g,
        print_time_per_plate_hrs=body.print_time_per_plate_hrs,
        labor_mins=body.labor_mins,
        design_time_hrs=body.design_time_hrs or Decimal(0),
        shipping_cost=body.shipping_cost,
        target_margin_pct=body.target_margin_pct,
    )
    job = Job(
        **body.model_dump(),
        total_pieces=body.qty_per_plate * body.num_plates,
        **costs,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: uuid.UUID, body: JobUpdate, db: DB):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    job.total_pieces = job.qty_per_plate * job.num_plates

    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=job.material_id,
        qty_per_plate=job.qty_per_plate,
        num_plates=job.num_plates,
        material_per_plate_g=job.material_per_plate_g,
        print_time_per_plate_hrs=job.print_time_per_plate_hrs,
        labor_mins=job.labor_mins,
        design_time_hrs=job.design_time_hrs or Decimal(0),
        shipping_cost=job.shipping_cost,
        target_margin_pct=job.target_margin_pct,
    )
    for k, v in costs.items():
        setattr(job, k, v)

    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: uuid.UUID, db: DB):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_deleted = True
    await db.commit()


@router.post("/calculate")
async def calculate_preview(body: CalculateRequest, db: DB):
    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=body.material_id,
        qty_per_plate=body.qty_per_plate,
        num_plates=body.num_plates,
        material_per_plate_g=body.material_per_plate_g,
        print_time_per_plate_hrs=body.print_time_per_plate_hrs,
        labor_mins=body.labor_mins,
        design_time_hrs=body.design_time_hrs or Decimal(0),
        shipping_cost=body.shipping_cost,
        target_margin_pct=body.target_margin_pct,
    )
    costs["total_pieces"] = body.qty_per_plate * body.num_plates
    # Convert Decimal to float for JSON serialization
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in costs.items()}
