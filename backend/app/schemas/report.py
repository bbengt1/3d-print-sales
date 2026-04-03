from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ── Inventory Report ──────────────────────────────────────────────


class StockLevelRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: str
    sku: str
    name: str
    stock_qty: int
    unit_cost: float
    stock_value: float
    reorder_point: int
    is_low_stock: bool


class InventoryReportResponse(BaseModel):
    stock_levels: list[StockLevelRow]
    total_stock_value: float
    total_products: int
    low_stock_count: int
    material_usage: list[dict]      # [{material, total_consumed_g, spool_cost}]
    turnover: list[dict]            # [{product, sku, sold_qty, stock_qty, turnover_rate}]


# ── Sales Report ─────────────────────────────────────────────────


class SalesReportRow(BaseModel):
    period: str         # e.g. "2026-03" or "2026-03-20"
    order_count: int
    gross_sales: float
    item_cogs: float
    gross_profit: float
    platform_fees: float
    shipping_costs: float
    contribution_margin: float


class ProductRanking(BaseModel):
    product_id: str | None
    description: str
    units_sold: int
    gross_sales: float
    item_cogs: float
    gross_profit: float
    platform_fees: float
    shipping_costs: float
    contribution_margin: float


class ChannelBreakdown(BaseModel):
    channel_name: str
    order_count: int
    gross_sales: float
    item_cogs: float
    gross_profit: float
    platform_fees: float
    shipping_costs: float
    contribution_margin: float


class PaymentMethodBreakdown(BaseModel):
    payment_method: str
    order_count: int
    gross_sales: float
    contribution_margin: float


class SalesReportResponse(BaseModel):
    period_data: list[SalesReportRow]
    top_products: list[ProductRanking]
    channel_breakdown: list[ChannelBreakdown]
    payment_method_breakdown: list[PaymentMethodBreakdown]
    total_orders: int
    gross_sales: float
    item_cogs: float
    gross_profit: float
    platform_fees: float
    shipping_costs: float
    contribution_margin: float
    net_profit: float | None = None


# ── Profit & Loss Report ─────────────────────────────────────────


class PLRow(BaseModel):
    period: str
    sales_revenue: float
    operational_production_estimate: float
    material_costs: float
    labor_costs: float
    machine_costs: float
    overhead_costs: float
    platform_fees: float
    shipping_costs: float
    total_costs: float
    gross_profit: float
    notes: str


class PLSummary(BaseModel):
    sales_revenue: float
    operational_production_estimate: float
    total_revenue: float
    material_costs: float
    labor_costs: float
    machine_costs: float
    overhead_costs: float
    platform_fees: float
    shipping_costs: float
    total_costs: float
    gross_profit: float
    profit_margin_pct: float
    reporting_basis: str
    production_estimate_note: str


class PLReportResponse(BaseModel):
    summary: PLSummary
    period_data: list[PLRow]
