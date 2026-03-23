"""Report generation service with date range filtering and period grouping."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.bill import Bill
from app.models.invoice import Invoice
from app.models.inventory_transaction import InventoryTransaction
from app.models.job import Job
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.payment import Payment
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel
from app.models.tax_profile import TaxProfile
from app.models.tax_remittance import TaxRemittance


def _trunc_period(d: date, period: str) -> str:
    """Truncate a date to a period key string."""
    if period == "daily":
        return d.isoformat()
    elif period == "weekly":
        # ISO week: YYYY-Www
        return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
    elif period == "yearly":
        return str(d.year)
    else:  # monthly (default)
        return f"{d.year}-{d.month:02d}"


# ── Inventory Report ──────────────────────────────────────────────


async def generate_inventory_report(db: AsyncSession, date_from: date | None, date_to: date | None):
    """Stock levels, valuation, material usage, and turnover."""
    # Stock levels
    result = await db.execute(
        select(Product).where(Product.is_active == True).order_by(Product.name)
    )
    products = result.scalars().all()

    stock_levels = []
    total_stock_value = 0.0
    low_stock_count = 0
    for p in products:
        val = float(p.unit_cost) * p.stock_qty
        is_low = p.stock_qty <= p.reorder_point
        if is_low:
            low_stock_count += 1
        total_stock_value += val
        stock_levels.append({
            "product_id": str(p.id),
            "sku": p.sku,
            "name": p.name,
            "stock_qty": p.stock_qty,
            "unit_cost": float(p.unit_cost),
            "stock_value": round(val, 2),
            "reorder_point": p.reorder_point,
            "is_low_stock": is_low,
        })

    # Material usage from inventory transactions (production type uses materials)
    mat_stmt = (
        select(
            Material.name,
            func.coalesce(func.sum(Job.material_per_plate_g * Job.num_plates), 0).label("total_g"),
            func.coalesce(func.sum(Job.material_cost), 0).label("total_cost"),
        )
        .join(Job, Job.material_id == Material.id)
        .where(Job.is_deleted == False)
    )
    if date_from:
        mat_stmt = mat_stmt.where(Job.date >= date_from)
    if date_to:
        mat_stmt = mat_stmt.where(Job.date <= date_to)
    mat_stmt = mat_stmt.group_by(Material.name).order_by(func.sum(Job.material_cost).desc())
    mat_result = await db.execute(mat_stmt)
    material_usage = [
        {"material": r.name, "total_consumed_g": round(float(r.total_g), 1), "spool_cost": round(float(r.total_cost), 2)}
        for r in mat_result.all()
    ]

    # Turnover: units sold (from sale_items) vs current stock
    turn_stmt = (
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.stock_qty,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("sold_qty"),
        )
        .outerjoin(SaleItem, SaleItem.product_id == Product.id)
        .outerjoin(Sale, Sale.id == SaleItem.sale_id)
        .where(Product.is_active == True)
    )
    # filter sales date range if provided
    if date_from:
        turn_stmt = turn_stmt.where((Sale.date >= date_from) | (Sale.id == None))
    if date_to:
        turn_stmt = turn_stmt.where((Sale.date <= date_to) | (Sale.id == None))
    turn_stmt = turn_stmt.where((Sale.is_deleted == False) | (Sale.id == None))
    turn_stmt = turn_stmt.group_by(Product.id, Product.name, Product.sku, Product.stock_qty)
    turn_result = await db.execute(turn_stmt)
    turnover = []
    for r in turn_result.all():
        avg_stock = (r.stock_qty + int(r.sold_qty)) / 2 if (r.stock_qty + int(r.sold_qty)) > 0 else 1
        rate = round(float(r.sold_qty) / avg_stock, 2) if avg_stock > 0 else 0
        turnover.append({
            "product": r.name,
            "sku": r.sku,
            "sold_qty": int(r.sold_qty),
            "stock_qty": r.stock_qty,
            "turnover_rate": rate,
        })
    turnover.sort(key=lambda x: x["turnover_rate"], reverse=True)

    return {
        "stock_levels": stock_levels,
        "total_stock_value": round(total_stock_value, 2),
        "total_products": len(products),
        "low_stock_count": low_stock_count,
        "material_usage": material_usage,
        "turnover": turnover,
    }


# ── Sales Report ─────────────────────────────────────────────────


async def generate_sales_report(
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
    period: str = "monthly",
):
    """Sales over time, top products, channel breakdown."""
    base = select(Sale).where(Sale.is_deleted == False)
    if date_from:
        base = base.where(Sale.date >= date_from)
    if date_to:
        base = base.where(Sale.date <= date_to)

    result = await db.execute(base.options(selectinload(Sale.items)).order_by(Sale.date))
    sales = result.scalars().all()

    completed = [s for s in sales if s.status not in ("cancelled", "refunded")]

    # Period data
    period_map: dict[str, dict] = {}
    for s in completed:
        key = _trunc_period(s.date, period)
        if key not in period_map:
            period_map[key] = {
                "order_count": 0,
                "gross_sales": 0.0,
                "item_cogs": 0.0,
                "gross_profit": 0.0,
                "platform_fees": 0.0,
                "shipping_costs": 0.0,
                "contribution_margin": 0.0,
            }
        period_map[key]["order_count"] += 1
        period_map[key]["gross_sales"] += float(s.total)
        item_cost = sum(float(i.unit_cost) * i.quantity for i in s.items)
        gross_profit = float(s.total) - item_cost
        period_map[key]["item_cogs"] += item_cost
        period_map[key]["gross_profit"] += gross_profit
        period_map[key]["platform_fees"] += float(s.platform_fees)
        period_map[key]["shipping_costs"] += float(s.shipping_cost)
        period_map[key]["contribution_margin"] += float(s.net_revenue)

    period_data = [
        {"period": k, **v} for k, v in sorted(period_map.items())
    ]

    # Top products
    prod_map: dict[str | None, dict] = {}
    for s in completed:
        for item in s.items:
            pid = str(item.product_id) if item.product_id else None
            desc = item.description
            if pid not in prod_map:
                prod_map[pid] = {
                    "product_id": pid,
                    "description": desc,
                    "units_sold": 0,
                    "gross_sales": 0.0,
                    "item_cogs": 0.0,
                    "gross_profit": 0.0,
                    "platform_fees": 0.0,
                    "shipping_costs": 0.0,
                    "contribution_margin": 0.0,
                }
            prod_map[pid]["units_sold"] += item.quantity
            line_rev = float(item.line_total)
            line_cost = float(item.unit_cost) * item.quantity
            sale_item_count = sum(i.quantity for i in s.items) or 1
            allocation_ratio = item.quantity / sale_item_count
            allocated_platform_fees = float(s.platform_fees) * allocation_ratio
            allocated_shipping_cost = float(s.shipping_cost) * allocation_ratio
            gross_profit = line_rev - line_cost
            contribution_margin = gross_profit - allocated_platform_fees - allocated_shipping_cost
            prod_map[pid]["gross_sales"] += line_rev
            prod_map[pid]["item_cogs"] += line_cost
            prod_map[pid]["gross_profit"] += gross_profit
            prod_map[pid]["platform_fees"] += allocated_platform_fees
            prod_map[pid]["shipping_costs"] += allocated_shipping_cost
            prod_map[pid]["contribution_margin"] += contribution_margin

    top_products = sorted(prod_map.values(), key=lambda x: x["gross_sales"], reverse=True)[:20]

    # Channel breakdown
    ch_map: dict[str, dict] = {}
    # Fetch channel names
    ch_ids = list(set(s.channel_id for s in completed if s.channel_id))
    channel_names: dict = {}
    if ch_ids:
        ch_result = await db.execute(select(SalesChannel).where(SalesChannel.id.in_(ch_ids)))
        for ch in ch_result.scalars().all():
            channel_names[ch.id] = ch.name

    for s in completed:
        ch_name = channel_names.get(s.channel_id, "Direct") if s.channel_id else "Direct"
        if ch_name not in ch_map:
            ch_map[ch_name] = {
                "channel_name": ch_name,
                "order_count": 0,
                "gross_sales": 0.0,
                "item_cogs": 0.0,
                "gross_profit": 0.0,
                "platform_fees": 0.0,
                "shipping_costs": 0.0,
                "contribution_margin": 0.0,
            }
        item_cogs = sum(float(i.unit_cost) * i.quantity for i in s.items)
        gross_profit = float(s.total) - item_cogs
        ch_map[ch_name]["order_count"] += 1
        ch_map[ch_name]["gross_sales"] += float(s.total)
        ch_map[ch_name]["item_cogs"] += item_cogs
        ch_map[ch_name]["gross_profit"] += gross_profit
        ch_map[ch_name]["platform_fees"] += float(s.platform_fees)
        ch_map[ch_name]["shipping_costs"] += float(s.shipping_cost)
        ch_map[ch_name]["contribution_margin"] += float(s.net_revenue)

    channel_breakdown = sorted(ch_map.values(), key=lambda x: x["gross_sales"], reverse=True)

    gross_sales = sum(float(s.total) for s in completed)
    item_cogs = sum(sum(float(i.unit_cost) * i.quantity for i in s.items) for s in completed)
    platform_fees = sum(float(s.platform_fees) for s in completed)
    shipping_costs = sum(float(s.shipping_cost) for s in completed)
    contribution_margin = sum(float(s.net_revenue) for s in completed)

    return {
        "period_data": period_data,
        "top_products": top_products,
        "channel_breakdown": channel_breakdown,
        "total_orders": len(completed),
        "gross_sales": round(gross_sales, 2),
        "item_cogs": round(item_cogs, 2),
        "gross_profit": round(gross_sales - item_cogs, 2),
        "platform_fees": round(platform_fees, 2),
        "shipping_costs": round(shipping_costs, 2),
        "contribution_margin": round(contribution_margin, 2),
        "net_profit": None,
    }


# ── P&L Report ───────────────────────────────────────────────────


async def generate_pl_report(
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
    period: str = "monthly",
):
    """Financial-style P&L driven by realized sales, with production estimates shown separately."""
    # Jobs data (operational production estimates/cost accumulation)
    job_stmt = select(Job).where(Job.is_deleted == False)
    if date_from:
        job_stmt = job_stmt.where(Job.date >= date_from)
    if date_to:
        job_stmt = job_stmt.where(Job.date <= date_to)
    job_result = await db.execute(job_stmt)
    jobs = job_result.scalars().all()

    # Sales data (realized revenue)
    sale_stmt = select(Sale).where(Sale.is_deleted == False)
    if date_from:
        sale_stmt = sale_stmt.where(Sale.date >= date_from)
    if date_to:
        sale_stmt = sale_stmt.where(Sale.date <= date_to)
    sale_result = await db.execute(sale_stmt.options(selectinload(Sale.items)))
    sales = sale_result.scalars().all()
    completed_sales = [s for s in sales if s.status not in ("cancelled", "refunded")]

    period_map: dict[str, dict] = {}

    for j in jobs:
        key = _trunc_period(j.date, period)
        if key not in period_map:
            period_map[key] = {
                "sales_revenue": 0.0,
                "operational_production_estimate": 0.0,
                "material_costs": 0.0,
                "labor_costs": 0.0,
                "machine_costs": 0.0,
                "overhead_costs": 0.0,
                "platform_fees": 0.0,
                "shipping_costs": 0.0,
            }
        period_map[key]["operational_production_estimate"] += float(j.total_revenue)
        period_map[key]["material_costs"] += float(j.material_cost)
        period_map[key]["labor_costs"] += float(j.labor_cost) + float(j.design_cost or 0)
        period_map[key]["machine_costs"] += float(j.machine_cost) + float(j.electricity_cost)
        period_map[key]["overhead_costs"] += float(j.overhead)

    for s in completed_sales:
        key = _trunc_period(s.date, period)
        if key not in period_map:
            period_map[key] = {
                "sales_revenue": 0.0,
                "operational_production_estimate": 0.0,
                "material_costs": 0.0,
                "labor_costs": 0.0,
                "machine_costs": 0.0,
                "overhead_costs": 0.0,
                "platform_fees": 0.0,
                "shipping_costs": 0.0,
            }
        period_map[key]["sales_revenue"] += float(s.total)
        period_map[key]["platform_fees"] += float(s.platform_fees)
        period_map[key]["shipping_costs"] += float(s.shipping_cost)

    period_data = []
    for k, v in sorted(period_map.items()):
        total_cost = v["material_costs"] + v["labor_costs"] + v["machine_costs"] + v["overhead_costs"] + v["platform_fees"] + v["shipping_costs"]
        period_data.append({
            "period": k,
            **v,
            "total_costs": round(total_cost, 2),
            "gross_profit": round(v["sales_revenue"] - total_cost, 2),
            "notes": "Revenue is sales-based only. Production estimate is shown separately for operational analysis.",
        })

    operational_production_estimate = sum(float(j.total_revenue) for j in jobs)
    sales_revenue = sum(float(s.total) for s in completed_sales)
    total_revenue = sales_revenue
    mat = sum(float(j.material_cost) for j in jobs)
    lab = sum(float(j.labor_cost) + float(j.design_cost or 0) for j in jobs)
    mach = sum(float(j.machine_cost) + float(j.electricity_cost) for j in jobs)
    overhead = sum(float(j.overhead) for j in jobs)
    pfees = sum(float(s.platform_fees) for s in completed_sales)
    ship = sum(float(s.shipping_cost) for s in completed_sales)
    total_costs = mat + lab + mach + overhead + pfees + ship
    gross_profit = total_revenue - total_costs

    summary = {
        "sales_revenue": round(sales_revenue, 2),
        "operational_production_estimate": round(operational_production_estimate, 2),
        "total_revenue": round(total_revenue, 2),
        "material_costs": round(mat, 2),
        "labor_costs": round(lab, 2),
        "machine_costs": round(mach, 2),
        "overhead_costs": round(overhead, 2),
        "platform_fees": round(pfees, 2),
        "shipping_costs": round(ship, 2),
        "total_costs": round(total_costs, 2),
        "gross_profit": round(gross_profit, 2),
        "profit_margin_pct": round(gross_profit / total_revenue * 100, 1) if total_revenue > 0 else 0,
        "reporting_basis": "sales_realized_revenue",
        "production_estimate_note": "Production estimate reflects job-side quoted/expected revenue and is excluded from total_revenue to avoid double counting.",
    }

    return {"summary": summary, "period_data": period_data}


# ── CSV Export ───────────────────────────────────────────────────


async def generate_ap_aging_report(db: AsyncSession, as_of_date: date):
    result = await db.execute(select(Bill).options(selectinload(Bill.vendor)).where(Bill.status != "void"))
    bills = result.scalars().all()
    rows = []
    totals = {"current": Decimal("0"), "bucket_1_30": Decimal("0"), "bucket_31_60": Decimal("0"), "bucket_61_90": Decimal("0"), "bucket_90_plus": Decimal("0")}
    for bill in bills:
        balance_due = (bill.amount or Decimal("0")) - (bill.amount_paid or Decimal("0"))
        if balance_due <= 0:
            continue
        due_date = bill.due_date or bill.issue_date
        age_days = max((as_of_date - due_date).days, 0)
        current = bucket_1_30 = bucket_31_60 = bucket_61_90 = bucket_90_plus = Decimal("0")
        if bill.due_date and as_of_date <= bill.due_date:
            current = balance_due
            totals["current"] += balance_due
        elif age_days <= 30:
            bucket_1_30 = balance_due
            totals["bucket_1_30"] += balance_due
        elif age_days <= 60:
            bucket_31_60 = balance_due
            totals["bucket_31_60"] += balance_due
        elif age_days <= 90:
            bucket_61_90 = balance_due
            totals["bucket_61_90"] += balance_due
        else:
            bucket_90_plus = balance_due
            totals["bucket_90_plus"] += balance_due
        rows.append({
            "bill_id": str(bill.id),
            "bill_number": bill.bill_number,
            "vendor_name": bill.vendor.name if bill.vendor else None,
            "due_date": bill.due_date,
            "balance_due": balance_due,
            "current": current,
            "bucket_1_30": bucket_1_30,
            "bucket_31_60": bucket_31_60,
            "bucket_61_90": bucket_61_90,
            "bucket_90_plus": bucket_90_plus,
        })
    return {"as_of_date": as_of_date, "rows": rows, **{k + '_total': v for k, v in totals.items()}, "total_outstanding": sum(totals.values(), Decimal('0'))}


async def generate_tax_liability_summary_report(db: AsyncSession, date_from: date | None, date_to: date | None):
    profiles = (await db.execute(select(TaxProfile).where(TaxProfile.is_active == True))).scalars().all()
    rows = []
    total_seller = total_marketplace = total_remitted = total_outstanding = Decimal("0")
    for profile in profiles:
        sale_stmt = select(Sale).where(Sale.tax_profile_id == profile.id, Sale.is_deleted == False)
        if date_from:
            sale_stmt = sale_stmt.where(Sale.date >= date_from)
        if date_to:
            sale_stmt = sale_stmt.where(Sale.date <= date_to)
        sales = (await db.execute(sale_stmt)).scalars().all()
        seller_collected = sum((sale.tax_collected for sale in sales if sale.tax_treatment == "seller_collected"), Decimal("0"))
        marketplace_facilitated = sum((sale.tax_collected for sale in sales if sale.tax_treatment == "marketplace_facilitated"), Decimal("0"))
        remit_stmt = select(TaxRemittance).where(TaxRemittance.tax_profile_id == profile.id)
        if date_from:
            remit_stmt = remit_stmt.where(TaxRemittance.period_end >= date_from)
        if date_to:
            remit_stmt = remit_stmt.where(TaxRemittance.period_start <= date_to)
        remitted = sum((row.amount for row in (await db.execute(remit_stmt)).scalars().all()), Decimal("0"))
        outstanding = seller_collected - remitted
        rows.append({
            "tax_profile_id": profile.id,
            "tax_profile_name": profile.name,
            "jurisdiction": profile.jurisdiction,
            "seller_collected": seller_collected,
            "marketplace_facilitated": marketplace_facilitated,
            "remitted": remitted,
            "outstanding_liability": outstanding,
        })
        total_seller += seller_collected
        total_marketplace += marketplace_facilitated
        total_remitted += remitted
        total_outstanding += outstanding
    return {
        "rows": rows,
        "total_seller_collected": total_seller,
        "total_marketplace_facilitated": total_marketplace,
        "total_remitted": total_remitted,
        "total_outstanding_liability": total_outstanding,
    }


async def generate_inventory_valuation_report(db: AsyncSession, date_from: date | None, date_to: date | None):
    stmt = select(MaterialReceipt).options(selectinload(MaterialReceipt.material)).order_by(MaterialReceipt.purchase_date.desc())
    if date_from:
        stmt = stmt.where(MaterialReceipt.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(MaterialReceipt.purchase_date <= date_to)
    receipts = (await db.execute(stmt)).scalars().all()
    rows = []
    total_inventory_value = Decimal("0")
    total_quantity = Decimal("0")
    for r in receipts:
        remaining_value = (r.quantity_remaining_g or Decimal("0")) * (r.landed_cost_per_g or Decimal("0"))
        rows.append({
            "material_id": str(r.material_id),
            "material_name": r.material.name if r.material else "Unknown",
            "receipt_id": str(r.id),
            "vendor_name": r.vendor_name,
            "purchase_date": r.purchase_date,
            "quantity_remaining_g": r.quantity_remaining_g,
            "landed_cost_per_g": r.landed_cost_per_g,
            "remaining_value": remaining_value,
        })
        total_inventory_value += remaining_value
        total_quantity += r.quantity_remaining_g or Decimal("0")
    return {"rows": rows, "total_inventory_value": total_inventory_value, "total_quantity_remaining_g": total_quantity}


async def generate_cogs_breakdown_report(db: AsyncSession, date_from: date | None, date_to: date | None, period: str = "monthly"):
    stmt = select(Sale).options(selectinload(Sale.items), selectinload(Sale.channel)).where(Sale.is_deleted == False)
    if date_from:
        stmt = stmt.where(Sale.date >= date_from)
    if date_to:
        stmt = stmt.where(Sale.date <= date_to)
    sales = (await db.execute(stmt)).scalars().all()
    bucket = {}
    total_units = 0
    total_cogs = Decimal("0")
    total_revenue = Decimal("0")
    for sale in sales:
        if sale.status in ("cancelled", "refunded"):
            continue
        channel_name = sale.channel.name if sale.channel else "Direct"
        for item in sale.items:
            key = (_trunc_period(sale.date, period), channel_name, item.description)
            row = bucket.setdefault(key, {"period": key[0], "channel_name": key[1], "product_description": key[2], "units_sold": 0, "cogs": Decimal("0"), "revenue": Decimal("0")})
            line_cogs = (item.unit_cost or Decimal("0")) * item.quantity
            line_revenue = item.line_total or Decimal("0")
            row["units_sold"] += item.quantity
            row["cogs"] += line_cogs
            row["revenue"] += line_revenue
            total_units += item.quantity
            total_cogs += line_cogs
            total_revenue += line_revenue
    return {"rows": list(bucket.values()), "total_units_sold": total_units, "total_cogs": total_cogs, "total_revenue": total_revenue}


async def _posted_journal_balances(db: AsyncSession, date_from: date | None = None, date_to: date | None = None):
    stmt = (
        select(Account.code, Account.name, Account.account_type, Account.normal_balance, JournalLine.entry_type, JournalLine.amount)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalEntry.status == "posted")
    )
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    rows = (await db.execute(stmt)).all()
    balances = {}
    for code, name, account_type, normal_balance, entry_type, amount in rows:
        key = (code, name, account_type, normal_balance)
        bal = balances.setdefault(key, Decimal("0"))
        if entry_type == normal_balance:
            balances[key] = bal + amount
        else:
            balances[key] = bal - amount
    return balances


async def generate_balance_sheet_report(db: AsyncSession, as_of_date: date):
    balances = await _posted_journal_balances(db, date_to=as_of_date)
    assets = []
    liabilities = []
    equity = []
    total_assets = total_liabilities = total_equity = Decimal("0")
    for (code, name, account_type, _), amount in balances.items():
        line = {"account_code": code, "account_name": name, "account_type": account_type, "amount": amount}
        if account_type == "asset":
            assets.append(line)
            total_assets += amount
        elif account_type == "liability":
            liabilities.append(line)
            total_liabilities += amount
        elif account_type == "equity":
            equity.append(line)
            total_equity += amount
    return {
        "as_of_date": as_of_date.isoformat(),
        "assets": {"lines": assets, "total": total_assets},
        "liabilities": {"lines": liabilities, "total": total_liabilities},
        "equity": {"lines": equity, "total": total_equity},
        "liabilities_and_equity_total": total_liabilities + total_equity,
        "is_balanced": total_assets == (total_liabilities + total_equity),
    }


async def generate_accrual_pl_report(db: AsyncSession, date_from: date | None, date_to: date | None):
    balances = await _posted_journal_balances(db, date_from=date_from, date_to=date_to)
    revenue = []
    cogs = []
    expenses = []
    total_revenue = total_cogs = total_expenses = Decimal("0")
    for (code, name, account_type, _), amount in balances.items():
        line = {"account_code": code, "account_name": name, "account_type": account_type, "amount": amount}
        if account_type == "revenue":
            revenue.append(line)
            total_revenue += amount
        elif account_type == "cogs":
            cogs.append(line)
            total_cogs += amount
        elif account_type == "expense":
            expenses.append(line)
            total_expenses += amount
    gross_profit = total_revenue - total_cogs
    net_income = gross_profit - total_expenses
    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "basis": "accrual",
        "revenue": {"lines": revenue, "total": total_revenue},
        "cogs": {"lines": cogs, "total": total_cogs},
        "expenses": {"lines": expenses, "total": total_expenses},
        "gross_profit": gross_profit,
        "net_income": net_income,
    }


async def generate_cash_pl_report(db: AsyncSession, date_from: date | None, date_to: date | None):
    revenue_total = Decimal("0")
    expense_total = Decimal("0")
    invoice_stmt = select(Invoice).where(Invoice.status != "void")
    if date_from:
        invoice_stmt = invoice_stmt.where(Invoice.issue_date >= date_from)
    if date_to:
        invoice_stmt = invoice_stmt.where(Invoice.issue_date <= date_to)
    invoices = (await db.execute(invoice_stmt)).scalars().all()
    revenue_total = sum((inv.amount_paid for inv in invoices), Decimal("0"))

    bill_stmt = select(Bill).where(Bill.status != "void")
    if date_from:
        bill_stmt = bill_stmt.where(Bill.issue_date >= date_from)
    if date_to:
        bill_stmt = bill_stmt.where(Bill.issue_date <= date_to)
    bills = (await db.execute(bill_stmt)).scalars().all()
    expense_total = sum((bill.amount_paid for bill in bills), Decimal("0"))

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "basis": "cash",
        "revenue": {"lines": [{"account_code": "cash", "account_name": "Cash Receipts", "account_type": "revenue", "amount": revenue_total}], "total": revenue_total},
        "cogs": {"lines": [], "total": Decimal("0")},
        "expenses": {"lines": [{"account_code": "cash", "account_name": "Cash Expenses", "account_type": "expense", "amount": expense_total}], "total": expense_total},
        "gross_profit": revenue_total,
        "net_income": revenue_total - expense_total,
    }


async def generate_cash_flow_summary_report(db: AsyncSession, date_from: date | None, date_to: date | None):
    payment_stmt = select(Payment)
    if date_from:
        payment_stmt = payment_stmt.where(Payment.payment_date >= date_from)
    if date_to:
        payment_stmt = payment_stmt.where(Payment.payment_date <= date_to)
    payments = (await db.execute(payment_stmt)).scalars().all()
    inflows = sum((payment.amount - payment.unapplied_amount for payment in payments), Decimal("0"))

    bill_stmt = select(Bill)
    if date_from:
        bill_stmt = bill_stmt.where(Bill.issue_date >= date_from)
    if date_to:
        bill_stmt = bill_stmt.where(Bill.issue_date <= date_to)
    bills = (await db.execute(bill_stmt)).scalars().all()
    outflows = sum((bill.amount_paid for bill in bills), Decimal("0"))

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "operating": {"total": inflows - outflows},
        "investing": {"total": Decimal("0")},
        "financing": {"total": Decimal("0")},
        "net_change_in_cash": inflows - outflows,
    }


def export_to_csv(rows: list[dict], columns: list[str] | None = None) -> str:
    """Convert a list of dicts to CSV string."""
    if not rows:
        return ""
    cols = columns or list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in cols})
    return output.getvalue()
