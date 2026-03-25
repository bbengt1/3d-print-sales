from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.models.job import Job
from app.models.printer import Printer
from app.schemas.job import (
    CalculateRequest,
    CalculateResponse,
    JobCreate,
    JobResponse,
    JobStatus,
    JobUpdate,
    PaginatedJobs,
)
from app.services.cost_calculator import CostCalculator
from app.services.inventory_service import add_inventory_from_job
from app.services.job_service import build_duplicate_job_create, generate_job_number

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "",
    response_model=PaginatedJobs,
    summary="List jobs",
    description="Returns paginated print jobs with filtering by status, material, customer, date range, and product name search.",
)
async def list_jobs(
    db: DB,
    status: JobStatus | None = Query(None, description="Filter by job status"),
    material_id: uuid.UUID | None = Query(None, description="Filter by material ID"),
    customer_id: uuid.UUID | None = Query(None, description="Filter by customer ID"),
    printer_id: uuid.UUID | None = Query(None, description="Filter by printer ID"),
    date_from: datetime.date | None = Query(None, description="Start date (inclusive)"),
    date_to: datetime.date | None = Query(None, description="End date (inclusive)"),
    search: str | None = Query(None, description="Search by product name or job number"),
    sort_by: str = Query("date", description="Sort field", pattern="^(date|job_number|total_revenue|net_profit|created_at)$"),
    sort_dir: str = Query("desc", description="Sort direction", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    base = select(Job).options(selectinload(Job.printer)).where(Job.is_deleted == False)

    if status:
        base = base.where(Job.status == status.value)
    if material_id:
        base = base.where(Job.material_id == material_id)
    if customer_id:
        base = base.where(Job.customer_id == customer_id)
    if printer_id:
        base = base.where(Job.printer_id == printer_id)
    if date_from:
        base = base.where(Job.date >= date_from)
    if date_to:
        base = base.where(Job.date <= date_to)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            Job.product_name.ilike(pattern) | Job.job_number.ilike(pattern)
        )

    # Total count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Sorting
    sort_column = getattr(Job, sort_by, Job.date)
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()

    result = await db.execute(base.order_by(order).offset(skip).limit(limit))
    items = result.scalars().all()

    return PaginatedJobs(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/next-number",
    summary="Get next job number",
    description="Preview the next available job number for the provided job date using YYYY.MM.DD.NNN sequencing.",
)
async def get_next_job_number(
    db: DB,
    date: datetime.date = Query(..., description="Job date to generate the next sequence for"),
):
    return {"job_number": await generate_job_number(db, date)}


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job by ID",
    description="Retrieve a single job with its full cost breakdown, pricing, and profit analysis.",
)
async def get_job(job_id: uuid.UUID, db: DB):
    result = await db.execute(
        select(Job).options(selectinload(Job.printer)).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "",
    response_model=JobResponse,
    status_code=201,
    summary="Create a job",
    description="Create a new print job. All cost fields (electricity, material, labor, etc.) are automatically calculated from the input parameters and current business settings/rates.",
)
async def create_job(body: JobCreate, user: CurrentUser, db: DB):
    job_number = body.job_number or await generate_job_number(db, body.date)

    if body.printer_id:
        printer_exists = await db.execute(select(Printer.id).where(Printer.id == body.printer_id))
        if not printer_exists.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Printer not found")

    # Check for duplicate job number
    existing = await db.execute(select(Job.id).where(Job.job_number == job_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Job number '{job_number}' already exists")

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
    # Exclude shipping_cost from body since it's included in calculated costs
    body_data = body.model_dump(exclude={"shipping_cost"})
    body_data["job_number"] = job_number
    job = Job(
        **body_data,
        total_pieces=body.qty_per_plate * body.num_plates,
        **costs,
    )
    db.add(job)
    await db.flush()

    # Auto-add to inventory if job is completed and linked to a product
    if job.product_id and job.status == "completed":
        await add_inventory_from_job(
            db=db,
            product_id=job.product_id,
            job_id=job.id,
            quantity=job.total_pieces,
            unit_cost=job.cost_per_piece,
            user_id=user.id,
        )
        job.inventory_added = True

    await db.commit()
    result = await db.execute(select(Job).options(selectinload(Job.printer)).execution_options(populate_existing=True).where(Job.id == job.id))
    return result.scalar_one()


@router.put(
    "/{job_id}",
    response_model=JobResponse,
    summary="Update a job",
    description="Update one or more fields of a job. Costs are automatically recalculated when print parameters change.",
)
async def update_job(job_id: uuid.UUID, body: JobUpdate, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Job).options(selectinload(Job.printer)).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check unique job_number if it's being changed
    if body.job_number and body.job_number != job.job_number:
        existing = await db.execute(
            select(Job.id).where(Job.job_number == body.job_number, Job.id != job_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Job number '{body.job_number}' already exists")

    if body.printer_id:
        printer_exists = await db.execute(select(Printer.id).where(Printer.id == body.printer_id))
        if not printer_exists.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Printer not found")

    old_status = job.status
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

    # Auto-add to inventory when status changes to completed
    if (
        job.product_id
        and job.status == "completed"
        and old_status != "completed"
        and not job.inventory_added
    ):
        await add_inventory_from_job(
            db=db,
            product_id=job.product_id,
            job_id=job.id,
            quantity=job.total_pieces,
            unit_cost=job.cost_per_piece,
            user_id=user.id,
        )
        job.inventory_added = True

    await db.commit()
    result = await db.execute(select(Job).options(selectinload(Job.printer)).execution_options(populate_existing=True).where(Job.id == job.id))
    return result.scalar_one()


@router.post(
    "/{job_id}/duplicate",
    response_model=JobResponse,
    status_code=201,
    summary="Duplicate a job",
    description="Create a new draft job by copying the editable inputs from an existing job and generating a new job number.",
)
async def duplicate_job(job_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Job).options(selectinload(Job.printer)).where(Job.id == job_id, Job.is_deleted == False)
    )
    source_job = result.scalar_one_or_none()
    if not source_job:
        raise HTTPException(status_code=404, detail="Job not found")

    new_job_number = await generate_job_number(db)
    duplicate_body = build_duplicate_job_create(source_job, job_number=new_job_number)

    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=duplicate_body.material_id,
        qty_per_plate=duplicate_body.qty_per_plate,
        num_plates=duplicate_body.num_plates,
        material_per_plate_g=duplicate_body.material_per_plate_g,
        print_time_per_plate_hrs=duplicate_body.print_time_per_plate_hrs,
        labor_mins=duplicate_body.labor_mins,
        design_time_hrs=duplicate_body.design_time_hrs or Decimal(0),
        shipping_cost=duplicate_body.shipping_cost,
        target_margin_pct=duplicate_body.target_margin_pct,
    )

    body_data = duplicate_body.model_dump(exclude={"shipping_cost"})
    job = Job(
        **body_data,
        total_pieces=duplicate_body.qty_per_plate * duplicate_body.num_plates,
        inventory_added=False,
        **costs,
    )
    db.add(job)
    await db.commit()
    result = await db.execute(select(Job).options(selectinload(Job.printer)).execution_options(populate_existing=True).where(Job.id == job.id))
    return result.scalar_one()


@router.delete(
    "/{job_id}",
    status_code=204,
    summary="Delete a job",
    description="Soft-deletes a job by marking it as deleted. The record is preserved for historical reporting.",
)
async def delete_job(job_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_deleted = True
    await db.commit()


@router.post(
    "/calculate",
    response_model=CalculateResponse,
    summary="Preview cost calculation",
    description="Run the cost calculation engine without saving a job. Use this for the live cost preview in the job form or the standalone calculator.",
)
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
    return CalculateResponse(
        total_pieces=body.qty_per_plate * body.num_plates,
        **{k: float(v) if isinstance(v, Decimal) else v for k, v in costs.items()},
    )
