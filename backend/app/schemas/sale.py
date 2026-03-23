from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class SaleStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    refunded = "refunded"
    cancelled = "cancelled"


class SaleItemCreate(BaseModel):
    product_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    description: str = Field(..., min_length=1, max_length=200, examples=["Phone Stand"])
    quantity: int = Field(..., gt=0, examples=[2])
    unit_price: Decimal = Field(..., ge=0, examples=[8.99])
    unit_cost: Decimal = Field(Decimal(0), ge=0, examples=[3.50])


class SaleItemResponse(BaseModel):
    id: uuid.UUID
    sale_id: uuid.UUID
    product_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    unit_cost: Decimal
    created_at: datetime.datetime | None = None

    model_config = {"from_attributes": True}


class SaleCreate(BaseModel):
    date: datetime.date = Field(..., examples=["2026-03-20"])
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200, examples=["John Doe"])
    channel_id: uuid.UUID | None = None
    tax_profile_id: uuid.UUID | None = None
    tax_treatment: str = Field("seller_collected", pattern="^(seller_collected|marketplace_facilitated|non_taxable)$")
    shipping_charged: Decimal = Field(Decimal(0), ge=0, examples=[5.99])
    shipping_cost: Decimal = Field(Decimal(0), ge=0, examples=[4.50])
    tax_collected: Decimal = Field(Decimal(0), ge=0, examples=[0])
    payment_method: str | None = Field(None, max_length=50, examples=["card"])
    tracking_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=1000)
    status: SaleStatus = Field(SaleStatus.pending, examples=["paid"])
    items: list[SaleItemCreate] = Field(..., min_length=1)


class SaleUpdate(BaseModel):
    date: datetime.date | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=200)
    channel_id: uuid.UUID | None = None
    tax_profile_id: uuid.UUID | None = None
    tax_treatment: str | None = Field(None, pattern="^(seller_collected|marketplace_facilitated|non_taxable)$")
    shipping_charged: Decimal | None = Field(None, ge=0)
    shipping_cost: Decimal | None = Field(None, ge=0)
    tax_collected: Decimal | None = Field(None, ge=0)
    payment_method: str | None = Field(None, max_length=50)
    tracking_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=1000)
    status: SaleStatus | None = None


class SaleResponse(BaseModel):
    id: uuid.UUID
    sale_number: str
    date: datetime.date
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    channel_id: uuid.UUID | None = None
    tax_profile_id: uuid.UUID | None = None
    tax_treatment: str
    status: str
    subtotal: Decimal
    shipping_charged: Decimal
    shipping_cost: Decimal
    platform_fees: Decimal
    tax_collected: Decimal
    total: Decimal
    item_cogs: Decimal
    gross_profit: Decimal
    contribution_margin: Decimal
    payment_method: str | None = None
    tracking_number: str | None = None
    notes: str | None = None
    items: list[SaleItemResponse] = []
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


class SaleListResponse(BaseModel):
    """Lightweight sale for list views (no items)."""
    id: uuid.UUID
    sale_number: str
    date: datetime.date
    customer_name: str | None = None
    channel_id: uuid.UUID | None = None
    tax_profile_id: uuid.UUID | None = None
    tax_treatment: str | None = None
    status: str
    total: Decimal
    gross_profit: Decimal
    contribution_margin: Decimal
    item_count: int = 0
    created_at: datetime.datetime | None = None


class PaginatedSales(BaseModel):
    items: list[SaleListResponse]
    total: int
    skip: int
    limit: int


class SalesMetrics(BaseModel):
    total_sales: int
    gross_sales: float
    item_cogs: float
    gross_profit: float
    platform_fees: float
    shipping_costs: float
    contribution_margin: float
    net_profit: float | None = None
    total_units_sold: int
    avg_order_value: float
    refund_count: int
    refund_rate: float
    revenue_by_channel: list[dict]
