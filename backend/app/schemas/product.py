from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, examples=["Phone Stand"])
    description: str | None = Field(None, max_length=1000, examples=["Minimalist phone stand"])
    material_id: uuid.UUID
    upc: str | None = Field(None, max_length=14, examples=["012345678901"])
    unit_cost: Decimal = Field(Decimal(0), ge=0, examples=[3.50])
    unit_price: Decimal = Field(Decimal(0), ge=0, examples=[8.99])
    stock_qty: int = Field(0, ge=0, examples=[10])
    reorder_point: int = Field(5, ge=0, examples=[5])
    is_active: bool = Field(True)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    material_id: uuid.UUID | None = None
    upc: str | None = Field(None, max_length=14)
    unit_cost: Decimal | None = Field(None, ge=0)
    unit_price: Decimal | None = Field(None, ge=0)
    stock_qty: int | None = Field(None, ge=0)
    reorder_point: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    sku: str
    upc: str | None = None
    name: str
    description: str | None = None
    material_id: uuid.UUID
    unit_cost: Decimal
    unit_price: Decimal
    stock_qty: int
    reorder_point: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
    skip: int
    limit: int


class TransactionType(str, Enum):
    production = "production"
    sale = "sale"
    adjustment = "adjustment"
    return_ = "return"
    waste = "waste"


class InventoryTransactionCreate(BaseModel):
    product_id: uuid.UUID
    type: TransactionType = Field(..., examples=["adjustment"])
    quantity: int = Field(..., examples=[5], description="Positive to add, negative to remove")
    unit_cost: Decimal = Field(Decimal(0), ge=0, examples=[3.50])
    notes: str | None = Field(None, max_length=500, examples=["Manual stock adjustment"])


class InventoryTransactionResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    product_sku: str | None = None
    job_id: uuid.UUID | None = None
    type: str
    quantity: int
    unit_cost: Decimal
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_by_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedTransactions(BaseModel):
    items: list[InventoryTransactionResponse]
    total: int
    skip: int
    limit: int


class InventoryReconcileRequest(BaseModel):
    product_id: uuid.UUID
    counted_qty: int = Field(..., ge=0)
    reason: str = Field(..., min_length=3, max_length=255)
    notes: str | None = Field(None, max_length=500)


class InventoryReconcileResponse(BaseModel):
    product_id: uuid.UUID
    current_qty: int
    counted_qty: int
    variance: int
    approval_required: bool = False
    detail: str
    transaction: InventoryTransactionResponse | None = None


class InventoryAlert(BaseModel):
    type: str  # "product" or "material"
    id: uuid.UUID
    name: str
    sku: str | None = None
    current_stock: int
    reorder_point: int

    model_config = {"from_attributes": True}
