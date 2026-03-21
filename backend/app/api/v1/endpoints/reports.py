"""Reports endpoints: Inventory, Sales, P&L with CSV export."""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import DB
from app.schemas.report import (
    InventoryReportResponse,
    PLReportResponse,
    SalesReportResponse,
)
from app.services.report_service import (
    export_to_csv,
    generate_inventory_report,
    generate_pl_report,
    generate_sales_report,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Inventory Report ──────────────────────────────────────────────


@router.get(
    "/inventory",
    response_model=InventoryReportResponse,
    summary="Inventory report",
    description="Stock levels with valuation, material usage, and turnover rates.",
)
async def inventory_report(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
):
    return await generate_inventory_report(db, date_from, date_to)


@router.get(
    "/inventory/csv",
    summary="Export inventory report as CSV",
    description="Download stock levels as a CSV file.",
)
async def inventory_csv(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
):
    data = await generate_inventory_report(db, date_from, date_to)
    csv_content = export_to_csv(
        data["stock_levels"],
        ["sku", "name", "stock_qty", "unit_cost", "stock_value", "reorder_point", "is_low_stock"],
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_report.csv"},
    )


# ── Sales Report ─────────────────────────────────────────────────


@router.get(
    "/sales",
    response_model=SalesReportResponse,
    summary="Sales report",
    description="Sales over time, top products, and channel breakdown.",
)
async def sales_report(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"]),
):
    return await generate_sales_report(db, date_from, date_to, period)


@router.get(
    "/sales/csv",
    summary="Export sales report as CSV",
    description="Download sales period data as a CSV file.",
)
async def sales_csv(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"]),
):
    data = await generate_sales_report(db, date_from, date_to, period)
    csv_content = export_to_csv(
        data["period_data"],
        ["period", "order_count", "gross_sales", "item_cogs", "gross_profit"],
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_report.csv"},
    )


# ── P&L Report ───────────────────────────────────────────────────


@router.get(
    "/pl",
    response_model=PLReportResponse,
    summary="Profit & Loss report",
    description="Combined P&L from production jobs and sales.",
)
async def pl_report(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"]),
):
    return await generate_pl_report(db, date_from, date_to, period)


@router.get(
    "/pl/csv",
    summary="Export P&L report as CSV",
    description="Download P&L period data as a CSV file.",
)
async def pl_csv(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"]),
):
    data = await generate_pl_report(db, date_from, date_to, period)
    csv_content = export_to_csv(
        data["period_data"],
        ["period", "production_revenue", "sales_revenue", "material_costs",
         "labor_costs", "machine_costs", "overhead_costs", "platform_fees",
         "shipping_costs", "gross_profit"],
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pl_report.csv"},
    )
