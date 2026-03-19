from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB
from app.models.material import Material

router = APIRouter(prefix="/materials", tags=["Materials"])


class MaterialResponse(BaseModel):
    id: uuid.UUID
    name: str
    brand: str
    spool_weight_g: Decimal
    spool_price: Decimal
    net_usable_g: Decimal
    cost_per_g: Decimal
    notes: str | None = None
    active: bool

    model_config = {"from_attributes": True}


class MaterialCreate(BaseModel):
    name: str
    brand: str
    spool_weight_g: Decimal
    spool_price: Decimal
    net_usable_g: Decimal
    notes: str | None = None
    active: bool = True


class MaterialUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    spool_weight_g: Decimal | None = None
    spool_price: Decimal | None = None
    net_usable_g: Decimal | None = None
    notes: str | None = None
    active: bool | None = None


@router.get("", response_model=list[MaterialResponse])
async def list_materials(db: DB, active: bool | None = Query(None)):
    stmt = select(Material)
    if active is not None:
        stmt = stmt.where(Material.active == active)
    result = await db.execute(stmt.order_by(Material.name))
    return result.scalars().all()


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: uuid.UUID, db: DB):
    result = await db.execute(select(Material).where(Material.id == material_id))
    mat = result.scalar_one_or_none()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    return mat


@router.post("", response_model=MaterialResponse, status_code=201)
async def create_material(body: MaterialCreate, db: DB):
    cost_per_g = body.spool_price / body.net_usable_g if body.net_usable_g else Decimal(0)
    mat = Material(**body.model_dump(), cost_per_g=cost_per_g)
    db.add(mat)
    await db.commit()
    await db.refresh(mat)
    return mat


@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(material_id: uuid.UUID, body: MaterialUpdate, db: DB):
    result = await db.execute(select(Material).where(Material.id == material_id))
    mat = result.scalar_one_or_none()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mat, field, value)
    if mat.net_usable_g:
        mat.cost_per_g = mat.spool_price / mat.net_usable_g
    await db.commit()
    await db.refresh(mat)
    return mat


@router.delete("/{material_id}", status_code=204)
async def delete_material(material_id: uuid.UUID, db: DB):
    result = await db.execute(select(Material).where(Material.id == material_id))
    mat = result.scalar_one_or_none()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    mat.active = False
    await db.commit()
