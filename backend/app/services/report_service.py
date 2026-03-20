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

from app.models.inventory_transaction import InventoryTransaction
from app.models.job import Job
from app.models.material import Material
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel


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
            period_map[key] = {"order_count": 0, "revenue": 0.0, "cost": 0.0, "profit": 0.0}
        period_map[key]["order_count"] += 1
        period_map[key]["revenue"] += float(s.total)
        item_cost = sum(float(i.unit_cost) * i.quantity for i in s.items)
        period_map[key]["cost"] += item_cost
        period_map[key]["profit"] += float(s.net_revenue) - item_cost

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
                prod_map[pid] = {"product_id": pid, "description": desc, "units_sold": 0, "revenue": 0.0, "cost": 0.0, "profit": 0.0}
            prod_map[pid]["units_sold"] += item.quantity
            line_rev = float(item.line_total)
            line_cost = float(item.unit_cost) * item.quantity
            prod_map[pid]["revenue"] += line_rev
            prod_map[pid]["cost"] += line_cost
            prod_map[pid]["profit"] += line_rev - line_cost

    top_products = sorted(prod_map.values(), key=lambda x: x["revenue"], reverse=True)[:20]

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
            ch_map[ch_name] = {"channel_name": ch_name, "order_count": 0, "revenue": 0.0, "platform_fees": 0.0, "net_revenue": 0.0}
        ch_map[ch_name]["order_count"] += 1
        ch_map[ch_name]["revenue"] += float(s.total)
        ch_map[ch_name]["platform_fees"] += float(s.platform_fees)
        ch_map[ch_name]["net_revenue"] += float(s.net_revenue)

    channel_breakdown = sorted(ch_map.values(), key=lambda x: x["revenue"], reverse=True)

    total_revenue = sum(float(s.total) for s in completed)
    total_cost = sum(sum(float(i.unit_cost) * i.quantity for i in s.items) for s in completed)

    return {
        "period_data": period_data,
        "top_products": top_products,
        "channel_breakdown": channel_breakdown,
        "total_orders": len(completed),
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_revenue - total_cost, 2),
    }


# ── P&L Report ───────────────────────────────────────────────────


async def generate_pl_report(
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
    period: str = "monthly",
):
    """Profit & Loss combining job costs and sales revenue."""
    # Jobs data
    job_stmt = select(Job).where(Job.is_deleted == False)
    if date_from:
        job_stmt = job_stmt.where(Job.date >= date_from)
    if date_to:
        job_stmt = job_stmt.where(Job.date <= date_to)
    job_result = await db.execute(job_stmt)
    jobs = job_result.scalars().all()

    # Sales data
    sale_stmt = select(Sale).where(Sale.is_deleted == False)
    if date_from:
        sale_stmt = sale_stmt.where(Sale.date >= date_from)
    if date_to:
        sale_stmt = sale_stmt.where(Sale.date <= date_to)
    sale_result = await db.execute(sale_stmt.options(selectinload(Sale.items)))
    sales = sale_result.scalars().all()
    completed_sales = [s for s in sales if s.status not in ("cancelled", "refunded")]

    # Build period data
    period_map: dict[str, dict] = {}

    for j in jobs:
        key = _trunc_period(j.date, period)
        if key not in period_map:
            period_map[key] = {
                "production_revenue": 0.0, "sales_revenue": 0.0,
                "material_costs": 0.0, "labor_costs": 0.0, "machine_costs": 0.0,
                "overhead_costs": 0.0, "platform_fees": 0.0, "shipping_costs": 0.0,
            }
        period_map[key]["production_revenue"] += float(j.total_revenue)
        period_map[key]["material_costs"] += float(j.material_cost)
        period_map[key]["labor_costs"] += float(j.labor_cost) + float(j.design_cost or 0)
        period_map[key]["machine_costs"] += float(j.machine_cost) + float(j.electricity_cost)
        period_map[key]["overhead_costs"] += float(j.overhead)

    for s in completed_sales:
        key = _trunc_period(s.date, period)
        if key not in period_map:
            period_map[key] = {
                "production_revenue": 0.0, "sales_revenue": 0.0,
                "material_costs": 0.0, "labor_costs": 0.0, "machine_costs": 0.0,
                "overhead_costs": 0.0, "platform_fees": 0.0, "shipping_costs": 0.0,
            }
        period_map[key]["sales_revenue"] += float(s.total)
        period_map[key]["platform_fees"] += float(s.platform_fees)
        period_map[key]["shipping_costs"] += float(s.shipping_cost)

    period_data = []
    for k, v in sorted(period_map.items()):
        total_rev = v["production_revenue"] + v["sales_revenue"]
        total_cost = v["material_costs"] + v["labor_costs"] + v["machine_costs"] + v["overhead_costs"] + v["platform_fees"] + v["shipping_costs"]
        period_data.append({
            "period": k,
            **v,
            "gross_profit": round(total_rev - total_cost, 2),
        })

    # Summary totals
    prod_rev = sum(float(j.total_revenue) for j in jobs)
    sales_rev = sum(float(s.total) for s in completed_sales)
    total_revenue = prod_rev + sales_rev
    mat = sum(float(j.material_cost) for j in jobs)
    lab = sum(float(j.labor_cost) + float(j.design_cost or 0) for j in jobs)
    mach = sum(float(j.machine_cost) + float(j.electricity_cost) for j in jobs)
    overhead = sum(float(j.overhead) for j in jobs)
    pfees = sum(float(s.platform_fees) for s in completed_sales)
    ship = sum(float(s.shipping_cost) for s in completed_sales)
    total_costs = mat + lab + mach + overhead + pfees + ship
    gross_profit = total_revenue - total_costs

    summary = {
        "production_revenue": round(prod_rev, 2),
        "sales_revenue": round(sales_rev, 2),
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
    }

    return {"summary": summary, "period_data": period_data}


# ── CSV Export ───────────────────────────────────────────────────


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
