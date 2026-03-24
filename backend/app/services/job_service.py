from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import JobCreate

_SEQUENCE_RE = re.compile(r"^(\d{4}\.\d{2}\.\d{2})\.(\d{3})$")


def build_job_number_prefix(job_date: date) -> str:
    return job_date.strftime("%Y.%m.%d.")


async def generate_job_number(db: AsyncSession, job_date: date | None = None) -> str:
    """Generate the next job number in YYYY.MM.DD.NNN format."""
    target_date = job_date or date.today()
    prefix = build_job_number_prefix(target_date)

    result = await db.execute(select(Job.job_number).where(Job.job_number.like(f"{prefix}%")))
    existing_numbers = result.scalars().all()

    max_sequence = 0
    for job_number in existing_numbers:
        match = _SEQUENCE_RE.match(job_number)
        if not match:
            continue
        if match.group(1) != prefix[:-1]:
            continue
        max_sequence = max(max_sequence, int(match.group(2)))

    return f"{prefix}{max_sequence + 1:03d}"


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
