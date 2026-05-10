from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.schemas.material import MaterialCreate, MaterialResponse, MaterialUpdate
from app.schemas.material_receipt import MaterialReceiptCreate, MaterialReceiptResponse
from app.services.material_receipt_service import create_material_receipt

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.get(
    "",
    response_model=list[MaterialResponse],
    summary="List materials",
    description="Returns filament materials with optional filtering by active status and search by name/brand. Supports pagination.",
)
async def list_materials(
    db: DB,
    active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by name or brand"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    stmt = select(Material)
    if active is not None:
        stmt = stmt.where(Material.active == active)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Material.name.ilike(pattern) | Material.brand.ilike(pattern))
    result = await db.execute(stmt.order_by(Material.name).offset(skip).limit(limit))
    return result.scalars().all()


@router.get(
    "/{material_id}",
    response_model=MaterialResponse,
    summary="Get material by ID",
    description="Retrieve a single filament material including its calculated cost per gram.",
)
async def get_material(material_id: uuid.UUID, db: DB):
    result = await db.execute(select(Material).where(Material.id == material_id))
    mat = result.scalar_one_or_none()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    return mat


@router.post(
    "",
    response_model=MaterialResponse,
    status_code=201,
    summary="Create a material",
    description="Add a new filament material. Cost per gram is automatically calculated from spool price and net usable grams.",
)
async def create_material(body: MaterialCreate, user: CurrentUser, db: DB):
    cost_per_g = body.spool_price / body.net_usable_g
    mat = Material(**body.model_dump(), cost_per_g=cost_per_g)
    db.add(mat)
    await db.commit()
    await db.refresh(mat)
    return mat


@router.put(
    "/{material_id}",
    response_model=MaterialResponse,
    summary="Update a material",
    description="Update one or more fields of a material. Cost per gram is recalculated if price or usable weight changes.",
)
async def update_material(material_id: uuid.UUID, body: MaterialUpdate, user: CurrentUser, db: DB):
    result = await db.execute(select(Material).where(Material.id == material_id))
    mat = result.scalar_one_or_none()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mat, field, value)
    if mat.net_usable_g and mat.net_usable_g > 0:
        mat.cost_per_g = mat.spool_price / mat.net_usable_g
    await db.commit()
    await db.refresh(mat)
    return mat


@router.get(
    "/{material_id}/receipts",
    response_model=list[MaterialReceiptResponse],
    summary="List material receipts/lots",
)
async def list_material_receipts(material_id: uuid.UUID, db: DB):
    material = (await db.execute(select(Material).where(Material.id == material_id))).scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    result = await db.execute(
        select(MaterialReceipt)
        .where(MaterialReceipt.material_id == material_id)
        .order_by(MaterialReceipt.purchase_date.desc(), MaterialReceipt.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/{material_id}/receipts",
    response_model=MaterialReceiptResponse,
    status_code=201,
    summary="Create material receipt/lot",
)
async def create_receipt(material_id: uuid.UUID, body: MaterialReceiptCreate, user: CurrentUser, db: DB):
    material = (await db.execute(select(Material).where(Material.id == material_id))).scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    receipt = await create_material_receipt(db, material=material, payload=body)
    return receipt


@router.delete(
    "/{material_id}",
    status_code=204,
    summary="Deactivate a material",
    description="Soft-deletes a material by setting active=false. Historical job data referencing this material is preserved.",
)
async def delete_material(material_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(Material).where(Material.id == material_id))
    mat = result.scalar_one_or_none()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    mat.active = False
    await db.commit()


# ---------- #230: catalog loaded filament from prints ----------


from decimal import Decimal as _Decimal

from pydantic import BaseModel as _BaseModel, Field as _Field


class FilamentResolveRequest(_BaseModel):
    name: str = _Field(..., min_length=1, max_length=120)
    brand: str | None = _Field(None, max_length=120)
    color: str | None = None
    spool_id: str | None = None
    source: str = _Field("print_job", description="print_job | slicer_metadata | printer_telemetry | csv_import | opening_balance")
    source_printer_id: str | None = None
    source_job_id: str | None = None
    spool_weight_g: _Decimal | None = None
    spool_price: _Decimal | None = None
    net_usable_g: _Decimal | None = None
    cost_per_g: _Decimal | None = None


@router.post(
    "/resolve-from-print",
    summary="#230: Resolve loaded filament against catalog; create review-needed entry on miss",
)
async def resolve_filament(body: FilamentResolveRequest, user: CurrentUser, db: DB):
    from app.services.filament_resolver import resolve_or_catalog

    try:
        result = await resolve_or_catalog(db, **body.model_dump())
    except ValueError as e:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result
