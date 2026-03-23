from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.ar import ARAgingRow
from app.schemas.tax import TaxLiabilityRow


class APAgingRow(BaseModel):
    bill_id: str
    bill_number: str | None = None
    vendor_name: str | None = None
    due_date: datetime.date | None = None
    balance_due: Decimal
    current: Decimal
    bucket_1_30: Decimal
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_90_plus: Decimal


class APAgingSummary(BaseModel):
    as_of_date: datetime.date
    rows: list[APAgingRow]
    current_total: Decimal
    bucket_1_30_total: Decimal
    bucket_31_60_total: Decimal
    bucket_61_90_total: Decimal
    bucket_90_plus_total: Decimal
    total_outstanding: Decimal


class InventoryValuationRow(BaseModel):
    material_id: str
    material_name: str
    receipt_id: str
    vendor_name: str
    purchase_date: datetime.date
    quantity_remaining_g: Decimal
    landed_cost_per_g: Decimal
    remaining_value: Decimal


class InventoryValuationSummary(BaseModel):
    rows: list[InventoryValuationRow]
    total_inventory_value: Decimal
    total_quantity_remaining_g: Decimal


class COGSBreakdownRow(BaseModel):
    period: str
    channel_name: str
    product_description: str
    units_sold: int
    cogs: Decimal
    revenue: Decimal


class COGSBreakdownSummary(BaseModel):
    rows: list[COGSBreakdownRow]
    total_units_sold: int
    total_cogs: Decimal
    total_revenue: Decimal


class TaxLiabilityReportResponse(BaseModel):
    rows: list[TaxLiabilityRow]
    total_seller_collected: Decimal
    total_marketplace_facilitated: Decimal
    total_remitted: Decimal
    total_outstanding_liability: Decimal


class ARAgingReportResponse(BaseModel):
    as_of_date: datetime.date
    rows: list[ARAgingRow]
    current_total: Decimal
    bucket_1_30_total: Decimal
    bucket_31_60_total: Decimal
    bucket_61_90_total: Decimal
    bucket_90_plus_total: Decimal
    total_outstanding: Decimal
