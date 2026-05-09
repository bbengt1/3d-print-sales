from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.kit_component import KitComponent
from app.models.product import Product


router = APIRouter(prefix="/kits", tags=["Kits"])


class KitComponentRow(BaseModel):
    component_product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)


class KitDefinitionRequest(BaseModel):
    components: list[KitComponentRow] = Field(..., min_length=1)


class KitComponentResponse(BaseModel):
    id: uuid.UUID
    component_product_id: uuid.UUID
    quantity: Decimal


class KitResponse(BaseModel):
    kit_product_id: uuid.UUID
    components: list[KitComponentResponse]


async def _ensure_product(db, product_id: uuid.UUID) -> Product:
    p = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return p


@router.get("/{kit_product_id}", response_model=KitResponse, summary="Get the kit definition for a product")
async def get_kit(kit_product_id: uuid.UUID, user: CurrentUser, db: DB):
    await _ensure_product(db, kit_product_id)
    rows = (
        await db.execute(
            select(KitComponent).where(KitComponent.kit_product_id == kit_product_id)
        )
    ).scalars().all()
    return KitResponse(
        kit_product_id=kit_product_id,
        components=[
            KitComponentResponse(
                id=r.id,
                component_product_id=r.component_product_id,
                quantity=Decimal(r.quantity),
            )
            for r in rows
        ],
    )


@router.put("/{kit_product_id}", response_model=KitResponse, summary="Define or replace the kit's component list")
async def upsert_kit(kit_product_id: uuid.UUID, body: KitDefinitionRequest, user: CurrentUser, db: DB):
    kit = await _ensure_product(db, kit_product_id)
    # Validate component products exist + none is the kit itself (no self-reference)
    for c in body.components:
        if c.component_product_id == kit_product_id:
            raise HTTPException(status_code=400, detail="A kit cannot include itself as a component")
        await _ensure_product(db, c.component_product_id)

    # Replace existing components for this kit (upsert semantics)
    existing = (
        await db.execute(
            select(KitComponent).where(KitComponent.kit_product_id == kit_product_id)
        )
    ).scalars().all()
    for r in existing:
        await db.delete(r)
    await db.flush()

    out_rows = []
    for c in body.components:
        kc = KitComponent(
            kit_product_id=kit_product_id,
            component_product_id=c.component_product_id,
            quantity=c.quantity,
        )
        db.add(kc)
        await db.flush()
        out_rows.append(
            KitComponentResponse(
                id=kc.id,
                component_product_id=kc.component_product_id,
                quantity=Decimal(kc.quantity),
            )
        )
    await db.commit()
    return KitResponse(kit_product_id=kit_product_id, components=out_rows)


@router.delete("/{kit_product_id}", status_code=204, summary="Remove all components (the product stops being a kit)")
async def clear_kit(kit_product_id: uuid.UUID, user: CurrentUser, db: DB):
    rows = (
        await db.execute(
            select(KitComponent).where(KitComponent.kit_product_id == kit_product_id)
        )
    ).scalars().all()
    for r in rows:
        await db.delete(r)
    await db.commit()


@router.get("", summary="List all kit products (products with at least one component)")
async def list_kits(user: CurrentUser, db: DB):
    rows = (
        await db.execute(
            select(KitComponent.kit_product_id).distinct()
        )
    ).scalars().all()
    return {"kit_product_ids": [str(r) for r in rows]}
