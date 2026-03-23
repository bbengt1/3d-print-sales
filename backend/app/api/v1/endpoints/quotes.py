from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.job import Job
from app.models.quote import Quote
from app.schemas.quote import (
    PaginatedQuotes,
    QuoteConvertToJob,
    QuoteCreate,
    QuoteResponse,
    QuoteStatus,
    QuoteUpdate,
)
from app.services.cost_calculator import CostCalculator

router = APIRouter(prefix="/quotes", tags=["Quotes"])


async def _calculate_quote_costs(db: DB, quote: QuoteCreate | Quote) -> dict:
    calc = CostCalculator(db)
    return await calc.calculate(
        material_id=quote.material_id,
        qty_per_plate=quote.qty_per_plate,
        num_plates=quote.num_plates,
        material_per_plate_g=quote.material_per_plate_g,
        print_time_per_plate_hrs=quote.print_time_per_plate_hrs,
        labor_mins=quote.labor_mins,
        design_time_hrs=quote.design_time_hrs or Decimal(0),
        shipping_cost=quote.shipping_cost,
        target_margin_pct=quote.target_margin_pct,
    )


@router.get("", response_model=PaginatedQuotes, summary="List quotes")
async def list_quotes(
    db: DB,
    status: QuoteStatus | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    base = select(Quote).where(Quote.is_deleted == False)
    if status:
        base = base.where(Quote.status == status.value)
    if customer_id:
        base = base.where(Quote.customer_id == customer_id)
    if search:
        pattern = f"%{search}%"
        base = base.where(Quote.quote_number.ilike(pattern) | Quote.product_name.ilike(pattern) | Quote.customer_name.ilike(pattern))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    result = await db.execute(base.order_by(Quote.date.desc(), Quote.created_at.desc()).offset(skip).limit(limit))
    items = result.scalars().all()
    return PaginatedQuotes(items=items, total=total, skip=skip, limit=limit)


@router.get("/{quote_id}", response_model=QuoteResponse, summary="Get quote by ID")
async def get_quote(quote_id: uuid.UUID, db: DB):
    quote = (await db.execute(select(Quote).where(Quote.id == quote_id, Quote.is_deleted == False))).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.post("", response_model=QuoteResponse, status_code=201, summary="Create quote")
async def create_quote(body: QuoteCreate, user: CurrentUser, db: DB):
    existing = await db.execute(select(Quote.id).where(Quote.quote_number == body.quote_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Quote number '{body.quote_number}' already exists")

    costs = await _calculate_quote_costs(db, body)
    quote = Quote(
        **body.model_dump(exclude={"shipping_cost"}),
        total_pieces=body.qty_per_plate * body.num_plates,
        **costs,
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote


@router.put("/{quote_id}", response_model=QuoteResponse, summary="Update quote")
async def update_quote(quote_id: uuid.UUID, body: QuoteUpdate, user: CurrentUser, db: DB):
    quote = (await db.execute(select(Quote).where(Quote.id == quote_id, Quote.is_deleted == False))).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "status":
            setattr(quote, field, value.value if hasattr(value, "value") else value)
        else:
            setattr(quote, field, value)

    quote.total_pieces = quote.qty_per_plate * quote.num_plates
    costs = await _calculate_quote_costs(db, quote)
    for key, value in costs.items():
        setattr(quote, key, value)

    await db.commit()
    await db.refresh(quote)
    return quote


@router.post("/{quote_id}/convert-to-job", response_model=dict, summary="Convert accepted quote to job")
async def convert_quote_to_job(quote_id: uuid.UUID, body: QuoteConvertToJob, user: CurrentUser, db: DB):
    quote = (await db.execute(select(Quote).where(Quote.id == quote_id, Quote.is_deleted == False))).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status != "accepted":
        raise HTTPException(status_code=400, detail="Only accepted quotes can be converted")
    if quote.job_id:
        raise HTTPException(status_code=400, detail="Quote has already been converted")

    existing_job = await db.execute(select(Job.id).where(Job.job_number == body.job_number))
    if existing_job.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Job number '{body.job_number}' already exists")

    job = Job(
        job_number=body.job_number,
        date=body.job_date or datetime.date.today(),
        customer_id=quote.customer_id,
        customer_name=quote.customer_name,
        product_name=quote.product_name,
        qty_per_plate=quote.qty_per_plate,
        num_plates=quote.num_plates,
        material_id=quote.material_id,
        total_pieces=quote.total_pieces,
        material_per_plate_g=quote.material_per_plate_g,
        print_time_per_plate_hrs=quote.print_time_per_plate_hrs,
        labor_mins=quote.labor_mins,
        design_time_hrs=quote.design_time_hrs,
        electricity_cost=quote.electricity_cost,
        material_cost=quote.material_cost,
        labor_cost=quote.labor_cost,
        design_cost=quote.design_cost,
        machine_cost=quote.machine_cost,
        packaging_cost=quote.packaging_cost,
        shipping_cost=quote.shipping_cost,
        failure_buffer=quote.failure_buffer,
        subtotal_cost=quote.subtotal_cost,
        overhead=quote.overhead,
        total_cost=quote.total_cost,
        cost_per_piece=quote.cost_per_piece,
        target_margin_pct=quote.target_margin_pct,
        price_per_piece=quote.price_per_piece,
        total_revenue=quote.total_revenue,
        platform_fees=quote.platform_fees,
        net_profit=quote.net_profit,
        profit_per_piece=quote.profit_per_piece,
        status=body.status,
    )
    db.add(job)
    await db.flush()
    quote.job_id = job.id
    await db.commit()
    return {"quote_id": str(quote.id), "job_id": str(job.id), "job_number": job.job_number}


@router.delete("/{quote_id}", status_code=204, summary="Delete quote")
async def delete_quote(quote_id: uuid.UUID, user: CurrentUser, db: DB):
    quote = (await db.execute(select(Quote).where(Quote.id == quote_id, Quote.is_deleted == False))).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote.is_deleted = True
    await db.commit()
