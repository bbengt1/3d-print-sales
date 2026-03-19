from __future__ import annotations

import datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB
from app.models.job import Job
from app.models.material import Material
from app.schemas.dashboard import (
    DashboardSummary,
    MaterialUsageDataPoint,
    ProfitMarginDataPoint,
    RevenueDataPoint,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _date_filter(stmt, date_from, date_to):
    if date_from:
        stmt = stmt.where(Job.date >= date_from)
    if date_to:
        stmt = stmt.where(Job.date <= date_to)
    return stmt


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Dashboard summary metrics",
    description="Returns aggregated business metrics: total jobs, pieces, revenue, costs, profit, average margin, and top material. Supports date range filtering.",
)
async def get_summary(
    db: DB,
    date_from: datetime.date | None = Query(None, description="Start date (inclusive)"),
    date_to: datetime.date | None = Query(None, description="End date (inclusive)"),
):
    stmt = select(
        func.count(Job.id).label("total_jobs"),
        func.coalesce(func.sum(Job.total_pieces), 0).label("total_pieces"),
        func.coalesce(func.sum(Job.total_revenue), 0).label("total_revenue"),
        func.coalesce(func.sum(Job.total_cost), 0).label("total_costs"),
        func.coalesce(func.sum(Job.platform_fees), 0).label("total_platform_fees"),
        func.coalesce(func.sum(Job.net_profit), 0).label("total_net_profit"),
    ).where(Job.is_deleted == False)
    stmt = _date_filter(stmt, date_from, date_to)

    result = await db.execute(stmt)
    row = result.one()

    total_pieces = int(row.total_pieces)
    total_revenue = float(row.total_revenue)
    total_net_profit = float(row.total_net_profit)

    avg_profit = total_net_profit / total_pieces if total_pieces > 0 else 0
    avg_margin = (total_net_profit / total_revenue * 100) if total_revenue > 0 else 0

    mat_stmt = (
        select(Material.name, func.count(Job.id).label("cnt"))
        .join(Job, Job.material_id == Material.id)
        .where(Job.is_deleted == False)
    )
    mat_stmt = _date_filter(mat_stmt, date_from, date_to)
    mat_stmt = mat_stmt.group_by(Material.name).order_by(func.count(Job.id).desc()).limit(1)

    mat_result = await db.execute(mat_stmt)
    mat_row = mat_result.one_or_none()

    return DashboardSummary(
        total_jobs=row.total_jobs,
        total_pieces=total_pieces,
        total_revenue=total_revenue,
        total_costs=float(row.total_costs),
        total_platform_fees=float(row.total_platform_fees),
        total_net_profit=total_net_profit,
        avg_profit_per_piece=avg_profit,
        avg_margin_pct=avg_margin,
        top_material=mat_row.name if mat_row else None,
    )


@router.get(
    "/charts/revenue",
    response_model=list[RevenueDataPoint],
    summary="Revenue over time",
    description="Returns daily revenue totals for charting. Supports date range filtering.",
)
async def revenue_chart(
    db: DB,
    date_from: datetime.date | None = Query(None, description="Start date (inclusive)"),
    date_to: datetime.date | None = Query(None, description="End date (inclusive)"),
):
    stmt = (
        select(Job.date, func.sum(Job.total_revenue).label("revenue"))
        .where(Job.is_deleted == False)
    )
    stmt = _date_filter(stmt, date_from, date_to)
    stmt = stmt.group_by(Job.date).order_by(Job.date)

    result = await db.execute(stmt)
    return [
        RevenueDataPoint(date=str(r.date), revenue=float(r.revenue))
        for r in result.all()
    ]


@router.get(
    "/charts/materials",
    response_model=list[MaterialUsageDataPoint],
    summary="Material usage breakdown",
    description="Returns job counts per material for pie/bar charts. Supports date range filtering.",
)
async def material_usage_chart(
    db: DB,
    date_from: datetime.date | None = Query(None, description="Start date (inclusive)"),
    date_to: datetime.date | None = Query(None, description="End date (inclusive)"),
):
    stmt = (
        select(Material.name, func.count(Job.id).label("job_count"))
        .join(Job, Job.material_id == Material.id)
        .where(Job.is_deleted == False)
    )
    stmt = _date_filter(stmt, date_from, date_to)
    stmt = stmt.group_by(Material.name).order_by(func.count(Job.id).desc())

    result = await db.execute(stmt)
    return [
        MaterialUsageDataPoint(material=r.name, count=r.job_count)
        for r in result.all()
    ]


@router.get(
    "/charts/profit-margins",
    response_model=list[ProfitMarginDataPoint],
    summary="Profit margin by job",
    description="Returns profit margin percentage per job for trend analysis. Supports date range filtering.",
)
async def profit_margin_chart(
    db: DB,
    date_from: datetime.date | None = Query(None, description="Start date (inclusive)"),
    date_to: datetime.date | None = Query(None, description="End date (inclusive)"),
):
    stmt = (
        select(Job.date, Job.job_number, Job.product_name, Job.net_profit, Job.total_revenue)
        .where(Job.is_deleted == False)
    )
    stmt = _date_filter(stmt, date_from, date_to)
    stmt = stmt.order_by(Job.date)

    result = await db.execute(stmt)
    return [
        ProfitMarginDataPoint(
            date=str(r.date),
            job=r.job_number,
            product=r.product_name,
            margin=float(r.net_profit / r.total_revenue * 100) if r.total_revenue else 0,
        )
        for r in result.all()
    ]
