from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.product import Product
from app.models.product_bom_item import ProductBOMItem
from app.schemas.product import (
    ProductBOMItemCreate,
    ProductBOMItemResponse,
    ProductBOMSummary,
)


class ProductBOMValidationError(ValueError):
    pass


async def get_product_or_raise(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise ProductBOMValidationError("Product not found")
    return product


async def _has_product_path(
    db: AsyncSession,
    *,
    start_product_id: uuid.UUID,
    target_product_id: uuid.UUID,
    seen: set[uuid.UUID] | None = None,
) -> bool:
    seen = seen or set()
    if start_product_id in seen:
        return False
    seen.add(start_product_id)

    rows = (
        await db.execute(
            select(ProductBOMItem.component_product_id).where(
                ProductBOMItem.product_id == start_product_id,
                ProductBOMItem.component_product_id.is_not(None),
            )
        )
    ).scalars().all()

    for child_id in rows:
        if child_id == target_product_id:
            return True
        if await _has_product_path(db, start_product_id=child_id, target_product_id=target_product_id, seen=seen):
            return True
    return False


async def _validate_item(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    item: ProductBOMItemCreate,
) -> None:
    if item.component_type == "material":
        if not item.material_id or item.component_product_id:
            raise ProductBOMValidationError("Material BOM rows must reference exactly one material.")
        material = (await db.execute(select(Material).where(Material.id == item.material_id))).scalar_one_or_none()
        if not material:
            raise ProductBOMValidationError("BOM material component not found.")
        return

    if item.component_type == "product":
        if not item.component_product_id or item.material_id:
            raise ProductBOMValidationError("Product BOM rows must reference exactly one component product.")
        if item.component_product_id == product_id:
            raise ProductBOMValidationError("A product cannot include itself in its BOM.")
        component = (
            await db.execute(select(Product).where(Product.id == item.component_product_id))
        ).scalar_one_or_none()
        if not component:
            raise ProductBOMValidationError("BOM product component not found.")
        if await _has_product_path(db, start_product_id=item.component_product_id, target_product_id=product_id):
            raise ProductBOMValidationError("BOM would create a circular product dependency.")
        return

    raise ProductBOMValidationError("Unsupported BOM component type.")


def _row_key(item: ProductBOMItemCreate) -> tuple[str, uuid.UUID | None, uuid.UUID | None]:
    return (item.component_type, item.material_id, item.component_product_id)


async def replace_product_bom(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    items: list[ProductBOMItemCreate],
) -> ProductBOMSummary:
    await get_product_or_raise(db, product_id)

    seen: set[tuple[str, uuid.UUID | None, uuid.UUID | None]] = set()
    for item in items:
        key = _row_key(item)
        if key in seen:
            raise ProductBOMValidationError("Duplicate BOM component rows are not allowed.")
        seen.add(key)
        await _validate_item(db, product_id=product_id, item=item)

    await db.execute(delete(ProductBOMItem).where(ProductBOMItem.product_id == product_id))
    for item in items:
        db.add(ProductBOMItem(product_id=product_id, **item.model_dump()))
    await db.commit()
    return await get_product_bom_summary(db, product_id=product_id)


def _material_available_quantity(material: Material, unit: str) -> Decimal:
    if unit.lower() in {"g", "gram", "grams"}:
        return Decimal(material.spools_in_stock or 0) * Decimal(material.net_usable_g or 0)
    return Decimal(material.spools_in_stock or 0)


def _material_unit_cost(material: Material, unit: str) -> Decimal:
    if unit.lower() in {"g", "gram", "grams"}:
        return Decimal(material.cost_per_g or 0)
    return Decimal(material.spool_price or 0)


def _required_quantity(item: ProductBOMItem) -> Decimal:
    return Decimal(item.quantity) * (Decimal("1") + (Decimal(item.waste_factor_pct or 0) / Decimal("100")))


async def _item_response(db: AsyncSession, item: ProductBOMItem) -> ProductBOMItemResponse:
    required = _required_quantity(item)
    blocker: str | None = None

    if item.component_type == "material" and item.material_id:
        material = (await db.execute(select(Material).where(Material.id == item.material_id))).scalar_one()
        available = _material_available_quantity(material, item.unit)
        unit_cost = _material_unit_cost(material, item.unit)
        estimated_cost = required * unit_cost
        if not material.active:
            blocker = "Material is inactive."
        elif available < required:
            blocker = "Insufficient material stock."
        return ProductBOMItemResponse(
            id=item.id,
            component_type="material",
            material_id=item.material_id,
            component_product_id=None,
            quantity=item.quantity,
            unit=item.unit,
            waste_factor_pct=item.waste_factor_pct,
            notes=item.notes,
            component_name=f"{material.name} ({material.brand})",
            component_sku=None,
            available_quantity=available,
            unit_cost=unit_cost,
            estimated_unit_cost=estimated_cost,
            is_blocked=blocker is not None,
            blocker=blocker,
        )

    component = (await db.execute(select(Product).where(Product.id == item.component_product_id))).scalar_one()
    available = Decimal(component.stock_qty or 0)
    unit_cost = Decimal(component.unit_cost or 0)
    estimated_cost = required * unit_cost
    if not component.is_active:
        blocker = "Component product is archived."
    elif available < required:
        blocker = "Insufficient component product stock."
    return ProductBOMItemResponse(
        id=item.id,
        component_type="product",
        material_id=None,
        component_product_id=item.component_product_id,
        quantity=item.quantity,
        unit=item.unit,
        waste_factor_pct=item.waste_factor_pct,
        notes=item.notes,
        component_name=component.name,
        component_sku=component.sku,
        available_quantity=available,
        unit_cost=unit_cost,
        estimated_unit_cost=estimated_cost,
        is_blocked=blocker is not None,
        blocker=blocker,
    )


async def get_product_bom_summary(db: AsyncSession, *, product_id: uuid.UUID) -> ProductBOMSummary:
    await get_product_or_raise(db, product_id)
    rows = (
        await db.execute(
            select(ProductBOMItem)
            .where(ProductBOMItem.product_id == product_id)
            .order_by(ProductBOMItem.created_at.asc(), ProductBOMItem.id.asc())
        )
    ).scalars().all()

    responses = [await _item_response(db, row) for row in rows]
    total_cost = sum((Decimal(row.estimated_unit_cost) for row in responses), Decimal("0"))
    blockers = [f"{row.component_name}: {row.blocker}" for row in responses if row.blocker]

    buildable: int | None = None
    if responses:
        buildable_values: list[int] = []
        for source, response in zip(rows, responses, strict=True):
            available = Decimal(response.available_quantity or 0)
            required = _required_quantity(source)
            buildable_values.append(int((available / required).to_integral_value(rounding=ROUND_FLOOR)))
        buildable = min(buildable_values)

    return ProductBOMSummary(
        product_id=product_id,
        items=responses,
        estimated_unit_cost=total_cost,
        buildable_quantity=buildable,
        blockers=blockers,
        has_bom=bool(responses),
    )
