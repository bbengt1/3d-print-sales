"""#262 P2: find-and-merge duplicate items (materials, products).

The operator picks a survivor and one or more duplicates; the service
rewrites every FK reference in the system to point at the survivor and
soft-deactivates the duplicates. Audit-log entries capture the merge.

Restrict to materials and products today — the same pattern can extend
to customers and vendors as a follow-up if needed.
"""
from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.inventory_location import InventoryTransferLine
from app.models.inventory_transaction import InventoryTransaction
from app.models.job import Job
from app.models.kit_component import KitComponent
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product
from app.models.product_bom_item import ProductBOMItem
from app.models.production_order import (
    FinishedGoodsLayer,
    ProductionOrder,
    ProductionOrderConsumption,
)
from app.models.quote import Quote
from app.models.sale_item import SaleItem


class MergeError(RuntimeError):
    pass


# (model, fk_column_name) per scope
MATERIAL_FK_TABLES = [
    (Job, "material_id"),
    (Quote, "material_id"),
    (Product, "material_id"),
    (MaterialReceipt, "material_id"),
    (ProductBOMItem, "material_id"),
    (ProductionOrderConsumption, "material_id"),
    (InventoryTransferLine, "material_id"),
]


PRODUCT_FK_TABLES = [
    (SaleItem, "product_id"),
    (InventoryTransaction, "product_id"),
    (ProductBOMItem, "product_id"),
    (ProductBOMItem, "component_product_id"),
    (KitComponent, "kit_product_id"),
    (KitComponent, "component_product_id"),
    (ProductionOrder, "product_id"),
    (FinishedGoodsLayer, "product_id"),
    (InventoryTransferLine, "product_id"),
]


async def _rewrite(
    db: AsyncSession,
    *,
    model,
    column_name: str,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
) -> int:
    column = getattr(model, column_name)
    res = await db.execute(
        update(model).where(column == from_id).values({column_name: to_id})
    )
    return res.rowcount or 0


async def merge_materials(
    db: AsyncSession,
    *,
    survivor_id: uuid.UUID,
    duplicate_ids: Iterable[uuid.UUID],
    actor_user_id: uuid.UUID | None = None,
) -> dict:
    return await _merge_generic(
        db,
        survivor_id=survivor_id,
        duplicate_ids=list(duplicate_ids),
        survivor_model=Material,
        scope_label="material",
        fk_tables=MATERIAL_FK_TABLES,
        soft_delete_field="active",
        actor_user_id=actor_user_id,
    )


async def merge_products(
    db: AsyncSession,
    *,
    survivor_id: uuid.UUID,
    duplicate_ids: Iterable[uuid.UUID],
    actor_user_id: uuid.UUID | None = None,
) -> dict:
    return await _merge_generic(
        db,
        survivor_id=survivor_id,
        duplicate_ids=list(duplicate_ids),
        survivor_model=Product,
        scope_label="product",
        fk_tables=PRODUCT_FK_TABLES,
        soft_delete_field="is_active",
        actor_user_id=actor_user_id,
    )


async def _merge_generic(
    db: AsyncSession,
    *,
    survivor_id: uuid.UUID,
    duplicate_ids: list[uuid.UUID],
    survivor_model,
    scope_label: str,
    fk_tables: list[tuple],
    soft_delete_field: str,
    actor_user_id: uuid.UUID | None,
) -> dict:
    if not duplicate_ids:
        raise MergeError("At least one duplicate id required")
    if survivor_id in duplicate_ids:
        raise MergeError("Survivor cannot also be a duplicate")

    survivor = (
        await db.execute(select(survivor_model).where(survivor_model.id == survivor_id))
    ).scalar_one_or_none()
    if survivor is None:
        raise MergeError(f"Survivor {scope_label} {survivor_id} not found")

    duplicates = (
        await db.execute(select(survivor_model).where(survivor_model.id.in_(duplicate_ids)))
    ).scalars().all()
    found_ids = {d.id for d in duplicates}
    missing = [str(i) for i in duplicate_ids if i not in found_ids]
    if missing:
        raise MergeError(f"Duplicates not found: {', '.join(missing)}")

    rewrites_per_dup: list[dict] = []
    for dup in duplicates:
        per_table: dict[str, int] = {}
        for model, col in fk_tables:
            n = await _rewrite(
                db, model=model, column_name=col,
                from_id=dup.id, to_id=survivor_id,
            )
            if n:
                table_label = f"{model.__tablename__}.{col}"
                per_table[table_label] = per_table.get(table_label, 0) + n
        # Soft-deactivate the duplicate
        setattr(dup, soft_delete_field, False)
        rewrites_per_dup.append({"id": str(dup.id), "name": dup.name, "rewrites": per_table})

        db.add(
            AuditLog(
                actor_user_id=actor_user_id,
                entity_type=scope_label,
                entity_id=str(dup.id),
                action="merge_duplicate",
                reason=f"merged into {survivor_id}",
                before_snapshot={"name": dup.name},
                after_snapshot={"survivor_id": str(survivor_id), "rewrites": per_table},
            )
        )
    await db.flush()
    return {
        "scope": scope_label,
        "survivor_id": str(survivor_id),
        "survivor_name": survivor.name,
        "merged": rewrites_per_dup,
    }
