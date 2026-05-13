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
from app.services.plate_service import (
    aggregate_plate_totals,
    build_plates_from_input,
    build_uniform_plates,
    is_uniform,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _job_load_options():
    return [selectinload(Job.printer), selectinload(Job.plates)]


@router.get("", response_model=PaginatedJobs, summary="List jobs")
async def list_jobs(
    db: DB,
    status: JobStatus | None = Query(None),
    material_id: uuid.UUID | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    printer_id: uuid.UUID | None = Query(None),
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("date", pattern="^(date|job_number|total_revenue|net_profit|created_at)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    base = select(Job).options(*_job_load_options()).where(Job.is_deleted == False)

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
        base = base.where(Job.product_name.ilike(pattern) | Job.job_number.ilike(pattern))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    sort_column = getattr(Job, sort_by, Job.date)
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()

    result = await db.execute(base.order_by(order).offset(skip).limit(limit))
    items = result.scalars().unique().all()
    return PaginatedJobs(items=items, total=total, skip=skip, limit=limit)


@router.get("/next-number", summary="Get next job number")
async def get_next_job_number(db: DB, date: datetime.date = Query(...)):
    return {"job_number": await generate_job_number(db, date)}


@router.get("/{job_id}", response_model=JobResponse, summary="Get job by ID")
async def get_job(job_id: uuid.UUID, db: DB):
    result = await db.execute(
        select(Job).options(*_job_load_options()).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _validate_printers(db: DB, printer_ids: list[uuid.UUID]) -> None:
    unique = [p for p in {pid for pid in printer_ids if pid is not None}]
    if not unique:
        return
    found = (await db.execute(select(Printer.id).where(Printer.id.in_(unique)))).scalars().all()
    if set(found) != set(unique):
        raise HTTPException(status_code=404, detail="Printer not found")


def _materialize_plates(body) -> tuple[list, bool]:
    """Return (plate_orm_list, is_mixed) from a JobCreate-ish body."""
    if body.plates:
        return build_plates_from_input(body.plates), True
    plates = build_uniform_plates(
        qty_per_plate=body.qty_per_plate,
        num_plates=body.num_plates,
        material_per_plate_g=Decimal(body.material_per_plate_g),
        print_time_per_plate_hrs=Decimal(body.print_time_per_plate_hrs),
        printer_id=body.printer_id,
    )
    return plates, False


@router.post("", response_model=JobResponse, status_code=201, summary="Create a job")
async def create_job(body: JobCreate, user: CurrentUser, db: DB):
    job_number = body.job_number or await generate_job_number(db, body.date)

    printer_ids = [body.printer_id] + [p.printer_id for p in (body.plates or [])]
    await _validate_printers(db, printer_ids)

    existing = await db.execute(select(Job.id).where(Job.job_number == job_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Job number '{job_number}' already exists")

    plate_rows, is_mixed = _materialize_plates(body)
    total_pieces, total_material_g, total_print_time_hrs = aggregate_plate_totals(plate_rows, mixed=is_mixed)

    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=body.material_id,
        labor_mins=body.labor_mins,
        design_time_hrs=body.design_time_hrs or Decimal(0),
        shipping_cost=body.shipping_cost,
        target_margin_pct=body.target_margin_pct,
        total_pieces=total_pieces,
        total_material_g=total_material_g,
        total_print_time_hrs=total_print_time_hrs,
    )

    body_data = body.model_dump(exclude={"shipping_cost", "plates"})
    body_data["job_number"] = job_number
    if is_mixed:
        body_data["qty_per_plate"] = None
        body_data["num_plates"] = None
        body_data["material_per_plate_g"] = None
        body_data["print_time_per_plate_hrs"] = None

    job = Job(
        **body_data,
        total_pieces=total_pieces,
        total_material_g=total_material_g,
        total_print_time_hrs=total_print_time_hrs,
        **costs,
    )
    job.plates = plate_rows
    db.add(job)
    await db.flush()

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
    result = await db.execute(
        select(Job).options(*_job_load_options()).execution_options(populate_existing=True).where(Job.id == job.id)
    )
    return result.scalar_one()


@router.put("/{job_id}", response_model=JobResponse, summary="Update a job")
async def update_job(job_id: uuid.UUID, body: JobUpdate, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Job).options(*_job_load_options()).where(Job.id == job_id, Job.is_deleted == False)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if body.job_number and body.job_number != job.job_number:
        existing = await db.execute(
            select(Job.id).where(Job.job_number == body.job_number, Job.id != job_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Job number '{body.job_number}' already exists")

    update_data = body.model_dump(exclude_unset=True)
    new_plates_payload = update_data.pop("plates", None)

    printer_ids: list[uuid.UUID | None] = []
    if "printer_id" in update_data and update_data["printer_id"] is not None:
        printer_ids.append(update_data["printer_id"])
    if new_plates_payload is not None:
        printer_ids.extend([p.printer_id for p in body.plates or []])
    await _validate_printers(db, [pid for pid in printer_ids if pid is not None])

    old_status = job.status
    for field, value in update_data.items():
        setattr(job, field, value)

    # Determine new plate set
    async def _replace_plates(fresh):
        if job.plates:
            for old in list(job.plates):
                await db.delete(old)
            job.plates = []
            await db.flush()
        job.plates = fresh

    if new_plates_payload is not None:
        # Caller supplied a fresh plate array — replace
        await _replace_plates(build_plates_from_input(body.plates or []))
        # Mixed mode: null out uniform conveniences unless they happen to be uniform
        uniform, qpp, npl, mpp, tpp = is_uniform(job.plates)
        if uniform:
            job.qty_per_plate = qpp
            job.num_plates = npl
            job.material_per_plate_g = mpp
            job.print_time_per_plate_hrs = tpp
        else:
            job.qty_per_plate = None
            job.num_plates = None
            job.material_per_plate_g = None
            job.print_time_per_plate_hrs = None
    else:
        # Uniform input updated — only regenerate plate rows if any uniform field changed
        uniform_keys = {"qty_per_plate", "num_plates", "material_per_plate_g", "print_time_per_plate_hrs", "printer_id"}
        if uniform_keys & set(update_data.keys()) and job.qty_per_plate is not None and job.num_plates is not None:
            await _replace_plates(
                build_uniform_plates(
                    qty_per_plate=int(job.qty_per_plate),
                    num_plates=int(job.num_plates),
                    material_per_plate_g=Decimal(job.material_per_plate_g or 0),
                    print_time_per_plate_hrs=Decimal(job.print_time_per_plate_hrs or 0),
                    printer_id=job.printer_id,
                )
            )

    is_mixed_now = job.qty_per_plate is None
    total_pieces, total_material_g, total_print_time_hrs = aggregate_plate_totals(job.plates, mixed=is_mixed_now)
    job.total_pieces = total_pieces
    job.total_material_g = total_material_g
    job.total_print_time_hrs = total_print_time_hrs

    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=job.material_id,
        labor_mins=job.labor_mins,
        design_time_hrs=job.design_time_hrs or Decimal(0),
        shipping_cost=job.shipping_cost,
        target_margin_pct=job.target_margin_pct,
        total_pieces=total_pieces,
        total_material_g=total_material_g,
        total_print_time_hrs=total_print_time_hrs,
    )
    for k, v in costs.items():
        setattr(job, k, v)

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
    result = await db.execute(
        select(Job).options(*_job_load_options()).execution_options(populate_existing=True).where(Job.id == job.id)
    )
    return result.scalar_one()


@router.post("/{job_id}/duplicate", response_model=JobResponse, status_code=201, summary="Duplicate a job")
async def duplicate_job(job_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(
        select(Job).options(*_job_load_options()).where(Job.id == job_id, Job.is_deleted == False)
    )
    source_job = result.scalar_one_or_none()
    if not source_job:
        raise HTTPException(status_code=404, detail="Job not found")

    new_job_number = await generate_job_number(db)

    # Clone plate rows from source
    cloned_plates = [
        # Build fresh ORM objects (cannot reuse source rows — they belong to source job)
        type(p)(
            plate_number=p.plate_number,
            printer_id=p.printer_id,
            parts_count=p.parts_count,
            material_g=p.material_g,
            print_time_hrs=p.print_time_hrs,
        )
        for p in source_job.plates
    ]

    source_is_mixed = source_job.qty_per_plate is None
    total_pieces, total_material_g, total_print_time_hrs = aggregate_plate_totals(cloned_plates, mixed=source_is_mixed)

    calc = CostCalculator(db)
    costs = await calc.calculate(
        material_id=source_job.material_id,
        labor_mins=source_job.labor_mins,
        design_time_hrs=source_job.design_time_hrs or Decimal(0),
        shipping_cost=source_job.shipping_cost,
        target_margin_pct=source_job.target_margin_pct,
        total_pieces=total_pieces,
        total_material_g=total_material_g,
        total_print_time_hrs=total_print_time_hrs,
    )

    job = Job(
        job_number=new_job_number,
        date=datetime.date.today(),
        customer_id=source_job.customer_id,
        customer_name=source_job.customer_name,
        product_name=source_job.product_name,
        qty_per_plate=source_job.qty_per_plate,
        num_plates=source_job.num_plates,
        material_id=source_job.material_id,
        material_per_plate_g=source_job.material_per_plate_g,
        print_time_per_plate_hrs=source_job.print_time_per_plate_hrs,
        total_pieces=total_pieces,
        total_material_g=total_material_g,
        total_print_time_hrs=total_print_time_hrs,
        labor_mins=source_job.labor_mins,
        design_time_hrs=source_job.design_time_hrs,
        target_margin_pct=source_job.target_margin_pct,
        product_id=source_job.product_id,
        printer_id=source_job.printer_id,
        status="draft",
        inventory_added=False,
        **costs,
    )
    job.plates = cloned_plates
    db.add(job)
    await db.commit()
    result = await db.execute(
        select(Job).options(*_job_load_options()).execution_options(populate_existing=True).where(Job.id == job.id)
    )
    return result.scalar_one()


@router.delete("/{job_id}", status_code=204, summary="Delete a job")
async def delete_job(job_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(Job).where(Job.id == job_id, Job.is_deleted == False))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_deleted = True
    await db.commit()


@router.post("/calculate", response_model=CalculateResponse, summary="Preview cost calculation")
async def calculate_preview(body: CalculateRequest, db: DB):
    calc = CostCalculator(db)
    total_pieces = body.qty_per_plate * body.num_plates
    total_material_g = Decimal(body.material_per_plate_g) * body.num_plates
    total_print_time_hrs = Decimal(body.print_time_per_plate_hrs) * body.num_plates
    costs = await calc.calculate(
        material_id=body.material_id,
        labor_mins=body.labor_mins,
        design_time_hrs=body.design_time_hrs or Decimal(0),
        shipping_cost=body.shipping_cost,
        target_margin_pct=body.target_margin_pct,
        total_pieces=total_pieces,
        total_material_g=total_material_g,
        total_print_time_hrs=total_print_time_hrs,
    )
    return CalculateResponse(
        total_pieces=total_pieces,
        **{k: float(v) if isinstance(v, Decimal) else v for k, v in costs.items()},
    )
