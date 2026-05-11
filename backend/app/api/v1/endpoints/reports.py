"""Reports endpoints: Inventory, Sales, P&L with CSV export."""
from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import DB
from app.schemas.finance_reports import (
    APAgingSummary,
    ARAgingReportResponse,
    COGSBreakdownSummary,
    InventoryValuationSummary,
    TaxLiabilityReportResponse,
)
from app.schemas.report import (
    InventoryReportResponse,
    PLReportResponse,
    SalesReportResponse,
)
from app.schemas.statements import (
    AccountDrillDownResponse,
    BalanceSheetResponse,
    CashFlowSummaryResponse,
    ProfitAndLossComparisonResponse,
    ProfitAndLossResponse,
)
from app.services.report_service import (
    export_to_csv,
    generate_accrual_pl_report,
    generate_ap_aging_report,
    generate_balance_sheet_report,
    generate_cash_flow_summary_report,
    generate_cash_pl_report,
    generate_cogs_breakdown_report,
    generate_inventory_report,
    generate_inventory_valuation_report,
    generate_pl_report,
    generate_receipts_payments_summary_report,
    generate_sales_report,
    generate_tax_liability_summary_report,
    generate_trial_balance_report,
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
    channel_id: uuid.UUID | None = Query(None),
    payment_method: str | None = Query(None),
    period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"]),
):
    return await generate_sales_report(db, date_from, date_to, period, channel_id, payment_method)


@router.get(
    "/sales/csv",
    summary="Export sales report as CSV",
    description="Download sales period data as a CSV file.",
)
async def sales_csv(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    channel_id: uuid.UUID | None = Query(None),
    payment_method: str | None = Query(None),
    period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"]),
):
    data = await generate_sales_report(db, date_from, date_to, period, channel_id, payment_method)
    csv_content = export_to_csv(
        data["period_data"],
        ["period", "order_count", "gross_sales", "item_cogs", "gross_profit", "platform_fees", "shipping_costs", "contribution_margin"],
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
        ["period", "sales_revenue", "operational_production_estimate", "material_costs",
         "labor_costs", "machine_costs", "overhead_costs", "platform_fees",
         "shipping_costs", "total_costs", "gross_profit", "notes"],
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pl_report.csv"},
    )


@router.get("/ar-aging", response_model=ARAgingReportResponse, summary="A/R aging report")
async def ar_aging_report(db: DB, as_of_date: datetime.date = Query(...)):
    # #322 P2: consolidated logic lives in report_service.compute_ar_aging.
    from app.services.report_service import compute_ar_aging
    return await compute_ar_aging(db, as_of_date)


@router.get(
    "/pl-comparison",
    response_model=ProfitAndLossComparisonResponse,
    summary="P&L for current period side-by-side with a prior period (#322 P2)",
)
async def pl_comparison_report(
    db: DB,
    date_from: datetime.date = Query(...),
    date_to: datetime.date = Query(...),
    compare_to_start: datetime.date = Query(...),
    compare_to_end: datetime.date = Query(...),
    basis: str = Query("accrual", pattern="^(accrual|cash)$"),
):
    from app.services.report_service import compute_pl_comparison

    current, prior, deltas = await compute_pl_comparison(
        db,
        date_from=date_from,
        date_to=date_to,
        compare_to_start=compare_to_start,
        compare_to_end=compare_to_end,
        basis=basis,
    )
    return ProfitAndLossComparisonResponse(current=current, prior=prior, deltas=deltas)


@router.get(
    "/account-drill-down",
    response_model=AccountDrillDownResponse,
    summary="List source journal lines behind a report cell (#322 P2)",
)
async def account_drill_down(
    db: DB,
    account_id: uuid.UUID = Query(...),
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
):
    from app.services.report_service import drill_down_account
    try:
        payload = await drill_down_account(db, account_id=account_id, date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AccountDrillDownResponse(**payload)


@router.get("/ap-aging", response_model=APAgingSummary, summary="A/P aging report")
async def ap_aging_report(db: DB, as_of_date: datetime.date = Query(...)):
    return await generate_ap_aging_report(db, as_of_date)


@router.get("/tax-liability", response_model=TaxLiabilityReportResponse, summary="Tax liability summary")
async def tax_liability_report(db: DB, date_from: datetime.date | None = Query(None), date_to: datetime.date | None = Query(None)):
    return await generate_tax_liability_summary_report(db, date_from, date_to)


@router.get("/inventory-valuation", response_model=InventoryValuationSummary, summary="Inventory valuation report")
async def inventory_valuation_report(db: DB, date_from: datetime.date | None = Query(None), date_to: datetime.date | None = Query(None)):
    return await generate_inventory_valuation_report(db, date_from, date_to)


@router.get("/cogs-breakdown", response_model=COGSBreakdownSummary, summary="COGS breakdown report")
async def cogs_breakdown_report(db: DB, date_from: datetime.date | None = Query(None), date_to: datetime.date | None = Query(None), period: str = Query("monthly", enum=["daily", "weekly", "monthly", "yearly"])):
    return await generate_cogs_breakdown_report(db, date_from, date_to, period)


@router.get("/balance-sheet", response_model=BalanceSheetResponse, summary="Balance sheet")
async def balance_sheet_report(db: DB, as_of_date: datetime.date = Query(...)):
    return await generate_balance_sheet_report(db, as_of_date)


@router.get("/cash-flow", response_model=CashFlowSummaryResponse, summary="Cash flow summary")
async def cash_flow_report(db: DB, date_from: datetime.date | None = Query(None), date_to: datetime.date | None = Query(None)):
    return await generate_cash_flow_summary_report(db, date_from, date_to)


@router.get("/pl-accrual", response_model=ProfitAndLossResponse, summary="Accrual-basis P&L")
async def pl_accrual_report(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
    division_id: uuid.UUID | None = Query(None, description="#328 P2: filter to one division"),
    project_id: uuid.UUID | None = Query(None, description="#328 P2: filter to one project"),
):
    return await generate_accrual_pl_report(
        db, date_from, date_to, division_id=division_id, project_id=project_id,
    )


@router.get("/pl-cash", response_model=ProfitAndLossResponse, summary="Cash-basis P&L")
async def pl_cash_report(db: DB, date_from: datetime.date | None = Query(None), date_to: datetime.date | None = Query(None)):
    return await generate_cash_pl_report(db, date_from, date_to)


@router.get("/trial-balance", summary="Trial balance — debit + credit columns at a point in time")
async def trial_balance_report(db: DB, as_of_date: datetime.date = Query(...)):
    return await generate_trial_balance_report(db, as_of_date)


@router.get(
    "/receipts-payments-summary",
    summary="Receipts & Payments Summary — categorized cash movements grouped by GL account",
)
async def receipts_payments_summary_report(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
):
    return await generate_receipts_payments_summary_report(db, date_from, date_to)


@router.get("/trial-balance.csv", summary="Trial balance as CSV")
async def trial_balance_csv(db: DB, as_of_date: datetime.date = Query(...)):
    from fastapi.responses import Response
    report = await generate_trial_balance_report(db, as_of_date)
    csv = export_to_csv(
        report["rows"],
        columns=["account_code", "account_name", "account_type", "debit", "credit"],
    )
    return Response(content=csv, media_type="text/csv")


@router.get("/receipts-payments-summary.csv", summary="Receipts & Payments Summary as CSV")
async def receipts_payments_csv(
    db: DB,
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
):
    from fastapi.responses import Response
    report = await generate_receipts_payments_summary_report(db, date_from, date_to)
    csv = export_to_csv(
        report["rows"],
        columns=["account_code", "account_name", "account_type", "is_bank_account", "inflows", "outflows", "net", "transaction_count"],
    )
    return Response(content=csv, media_type="text/csv")
