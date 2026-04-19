from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.product import Product
from app.schemas.product import (
    PaginatedProducts,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.inventory_service import generate_sku

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=PaginatedProducts,
    summary="List products",
    description="Returns paginated product catalog with filtering by active status, material, stock level, and search.",
)
async def list_products(
    db: DB,
    is_active: bool | None = Query(None, description="Filter by active status"),
    material_id: uuid.UUID | None = Query(None, description="Filter by material ID"),
    low_stock: bool | None = Query(None, description="Filter products below reorder point"),
    search: str | None = Query(None, description="Search by name, SKU, or UPC"),
    sort_by: str = Query(
        "name",
        description="Sort field (allowlisted)",
        pattern="^(name|sku|unit_price|unit_cost|stock_qty|reorder_point|created_at|updated_at)$",
    ),
    sort_dir: str = Query("asc", description="Sort direction", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    base = select(Product)
    if is_active is not None:
        base = base.where(Product.is_active == is_active)
    if material_id:
        base = base.where(Product.material_id == material_id)
    if low_stock:
        base = base.where(Product.stock_qty <= Product.reorder_point)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            Product.name.ilike(pattern) | Product.sku.ilike(pattern) | Product.upc.ilike(pattern)
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    sort_column = getattr(Product, sort_by, Product.name)
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    result = await db.execute(base.order_by(order).offset(skip).limit(limit))
    items = result.scalars().all()

    return PaginatedProducts(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product by ID",
    description="Retrieve a single product with its inventory details.",
)
async def get_product(product_id: uuid.UUID, db: DB):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
    summary="Create a product",
    description="Create a new product in the catalog. SKU is auto-generated in format PRD-{MATERIAL}-{NNNN}.",
)
async def create_product(body: ProductCreate, user: CurrentUser, db: DB):
    if body.upc:
        existing_upc = await db.execute(select(Product.id).where(Product.upc == body.upc))
        if existing_upc.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"UPC '{body.upc}' is already assigned to another product")
    sku = await generate_sku(db, body.material_id)
    product = Product(**body.model_dump(), sku=sku)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update a product",
    description="Update one or more fields of a product.",
)
async def update_product(product_id: uuid.UUID, body: ProductUpdate, user: CurrentUser, db: DB):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_unset=True)

    if "upc" in update_data and update_data["upc"]:
        existing_upc = await db.execute(
            select(Product.id).where(Product.id != product_id, Product.upc == update_data["upc"])
        )
        if existing_upc.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"UPC '{update_data['upc']}' is already assigned to another product")

    # If material changed, regenerate SKU
    if "material_id" in update_data and update_data["material_id"] != product.material_id:
        product.sku = await generate_sku(db, update_data["material_id"])

    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete(
    "/{product_id}",
    status_code=204,
    summary="Deactivate a product",
    description="Soft-deletes a product by setting is_active=false.",
)
async def delete_product(product_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    await db.commit()
