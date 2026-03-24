from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import JobCreate


async def generate_job_number(db: AsyncSession, job_date: date | None = None) -> str:
    """Generate a unique job number in format J-YYYY-NNNN."""
    target_date = job_date or date.today()
    prefix = f"J-{target_date.year}-"
    result = await db.execute(
        select(func.count()).select_from(Job).where(Job.job_number.like(f"{prefix}%"))
    )
    count = result.scalar() or 0
    return f"{prefix}{count + 1:04d}"


def build_duplicate_job_create(source: Job, *, job_number: str, job_date: date | None = None) -> JobCreate:
    """Map a source job into a new draft JobCreate payload."""
    return JobCreate(
        job_number=job_number,
        date=job_date or date.today(),
        customer_id=source.customer_id,
        customer_name=source.customer_name,
        product_name=source.product_name,
        qty_per_plate=source.qty_per_plate,
        num_plates=source.num_plates,
        material_id=source.material_id,
        material_per_plate_g=source.material_per_plate_g,
        print_time_per_plate_hrs=source.print_time_per_plate_hrs,
        labor_mins=source.labor_mins,
        design_time_hrs=source.design_time_hrs if source.design_time_hrs is not None else Decimal(0),
        shipping_cost=source.shipping_cost,
        target_margin_pct=source.target_margin_pct,
        product_id=source.product_id,
        status="draft",
    )
