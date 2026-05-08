from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field
from typing import Literal


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


class ProductBarcodeGenerateResponse(BaseModel):
    upc: str = Field(..., min_length=12, max_length=12, examples=["040000000013"])
    format: str = Field("upc-a", examples=["upc-a"])
    namespace: str = Field(..., examples=["internal-upc-a-04"])
    note: str


ProductBOMComponentType = Literal["material", "product", "supply"]


class ProductBOMItemBase(BaseModel):
    component_type: ProductBOMComponentType
    material_id: uuid.UUID | None = None
    component_product_id: uuid.UUID | None = None
    component_name: str | None = Field(None, min_length=1, max_length=200, examples=["M3 screw"])
    component_sku: str | None = Field(None, max_length=100, examples=["M3x12-BLK"])
    quantity: Decimal = Field(..., gt=0, examples=[Decimal("12.5")])
    unit: str = Field("each", min_length=1, max_length=20, examples=["g"])
    waste_factor_pct: Decimal = Field(Decimal(0), ge=0, examples=[Decimal("5")])
    unit_cost: Decimal | None = Field(None, ge=0, examples=[Decimal("0.08")])
    available_quantity: Decimal | None = Field(None, ge=0, examples=[Decimal("250")])
    notes: str | None = Field(None, max_length=500)


class ProductBOMItemCreate(ProductBOMItemBase):
    pass


class ProductBOMItemResponse(ProductBOMItemBase):
    id: uuid.UUID
    component_name: str
    component_sku: str | None = None
    available_quantity: Decimal | int | None = None
    unit_cost: Decimal
    estimated_unit_cost: Decimal
    is_blocked: bool = False
    blocker: str | None = None

    model_config = {"from_attributes": True}


class ProductBOMReplace(BaseModel):
    items: list[ProductBOMItemCreate] = Field(default_factory=list)


class ProductBOMSummary(BaseModel):
    product_id: uuid.UUID
    items: list[ProductBOMItemResponse]
    estimated_unit_cost: Decimal
    buildable_quantity: int | None
    blockers: list[str] = Field(default_factory=list)
    has_bom: bool


class ProductBOMAvailability(ProductBOMSummary):
    pass


class POSProductScanRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, examples=["012345678901"])


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
