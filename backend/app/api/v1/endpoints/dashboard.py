from __future__ import annotations

import datetime
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB
from app.models.bill import Bill
from app.models.invoice import Invoice
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.marketplace_settlement import MarketplaceSettlement
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.job import Job
from app.models.account import Account
from app.schemas.dashboard import (
    DashboardSummary,
    MaterialUsageDataPoint,
    ProfitMarginDataPoint,
    RevenueDataPoint,
)
from app.schemas.finance_dashboard import FinanceDashboardSummary

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


@router.get(
    "/finance-summary",
    response_model=FinanceDashboardSummary,
    summary="Finance dashboard summary",
    description="Returns finance-focused dashboard widgets for cash, receivables, payables, inventory, tax, and payouts in transit.",
)
async def finance_summary(db: DB):
    today = datetime.date.today()
    month_start = today.replace(day=1)

    cash_stmt = (
        select(Account.normal_balance, JournalLine.entry_type, JournalLine.amount)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalEntry.status == "posted", Account.code == "1000")
    )
    cash_rows = (await db.execute(cash_stmt)).all()
    cash_on_hand = Decimal("0")
    for normal_balance, entry_type, amount in cash_rows:
        cash_on_hand += amount if entry_type == normal_balance else -amount

    unpaid_invoices = (await db.execute(select(func.coalesce(func.sum(Invoice.balance_due), 0)).where(Invoice.status != "void"))).scalar_one()
    unpaid_bills = (await db.execute(select(func.coalesce(func.sum(Bill.amount - Bill.amount_paid), 0)).where(Bill.status != "void"))).scalar_one()

    income_stmt = (
        select(Account.account_type, Account.normal_balance, JournalLine.entry_type, JournalLine.amount)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalEntry.status == "posted", JournalEntry.entry_date >= month_start, JournalEntry.entry_date <= today, Account.account_type.in_(["revenue", "cogs", "expense"]))
    )
    income_rows = (await db.execute(income_stmt)).all()
    revenue = cogs = expenses = Decimal("0")
    for account_type, normal_balance, entry_type, amount in income_rows:
        signed = amount if entry_type == normal_balance else -amount
        if account_type == "revenue":
            revenue += signed
        elif account_type == "cogs":
            cogs += signed
        elif account_type == "expense":
            expenses += signed
    current_month_net_income = revenue - cogs - expenses

    inv_rows = (await db.execute(select(MaterialReceipt.quantity_remaining_g, MaterialReceipt.landed_cost_per_g))).all()
    inventory_asset_value = sum(((qty or Decimal("0")) * (cost or Decimal("0")) for qty, cost in inv_rows), Decimal("0"))

    tax_payable_stmt = (
        select(Account.normal_balance, JournalLine.entry_type, JournalLine.amount)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalEntry.status == "posted", Account.code == "2100")
    )
    tax_rows = (await db.execute(tax_payable_stmt)).all()
    tax_payable = Decimal("0")
    for normal_balance, entry_type, amount in tax_rows:
        tax_payable += amount if entry_type == normal_balance else -amount

    payouts_in_transit = (await db.execute(select(func.coalesce(func.sum(MarketplaceSettlement.expected_net), 0)).where(MarketplaceSettlement.payout_date > today))).scalar_one()

    return FinanceDashboardSummary(
        cash_on_hand=cash_on_hand,
        unpaid_invoices=unpaid_invoices,
        unpaid_bills=unpaid_bills,
        current_month_net_income=current_month_net_income,
        inventory_asset_value=inventory_asset_value,
        tax_payable=tax_payable,
        payouts_in_transit=payouts_in_transit,
    )
