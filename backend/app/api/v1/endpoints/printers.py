from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.printer import Printer
from app.schemas.printer import PaginatedPrinters, PrinterCreate, PrinterResponse, PrinterUpdate

router = APIRouter(prefix="/printers", tags=["Printers"])


@router.get(
    "",
    response_model=PaginatedPrinters,
    summary="List printers",
    description="Returns paginated printers with optional filtering by active status, printer status, and search.",
)
async def list_printers(
    db: DB,
    is_active: bool | None = Query(None, description="Filter by active status"),
    status: str | None = Query(None, description="Filter by printer status"),
    search: str | None = Query(None, description="Search by printer name, slug, model, or location"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    base = select(Printer)
    if is_active is not None:
        base = base.where(Printer.is_active == is_active)
    if status:
        base = base.where(Printer.status == status)
    if search:
        pattern = f"%{search}%"
        base = base.where(
            Printer.name.ilike(pattern)
            | Printer.slug.ilike(pattern)
            | Printer.model.ilike(pattern)
            | Printer.location.ilike(pattern)
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    result = await db.execute(base.order_by(Printer.name).offset(skip).limit(limit))
    items = result.scalars().all()
    return PaginatedPrinters(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{printer_id}",
    response_model=PrinterResponse,
    summary="Get printer by ID",
    description="Retrieve a single printer record.",
)
async def get_printer(printer_id: uuid.UUID, db: DB):
    result = await db.execute(select(Printer).where(Printer.id == printer_id))
    printer = result.scalar_one_or_none()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


@router.post(
    "",
    response_model=PrinterResponse,
    status_code=201,
    summary="Create a printer",
    description="Create a new tracked printer resource.",
)
async def create_printer(body: PrinterCreate, user: CurrentUser, db: DB):
    existing = await db.execute(select(Printer.id).where((Printer.name == body.name) | (Printer.slug == body.slug)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Printer name or slug already exists")

    printer = Printer(**body.model_dump())
    db.add(printer)
    await db.commit()
    await db.refresh(printer)
    return printer


@router.put(
    "/{printer_id}",
    response_model=PrinterResponse,
    summary="Update a printer",
    description="Update one or more fields of a printer.",
)
async def update_printer(printer_id: uuid.UUID, body: PrinterUpdate, user: CurrentUser, db: DB):
    result = await db.execute(select(Printer).where(Printer.id == printer_id))
    printer = result.scalar_one_or_none()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data or "slug" in update_data:
        existing = await db.execute(
            select(Printer.id).where(
                Printer.id != printer_id,
                ((Printer.name == update_data.get("name", printer.name)) | (Printer.slug == update_data.get("slug", printer.slug)))
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Printer name or slug already exists")

    for field, value in update_data.items():
        setattr(printer, field, value)

    await db.commit()
    await db.refresh(printer)
    return printer


@router.delete(
    "/{printer_id}",
    status_code=204,
    summary="Deactivate a printer",
    description="Soft-deletes a printer by setting is_active=false.",
)
async def delete_printer(printer_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(Printer).where(Printer.id == printer_id))
    printer = result.scalar_one_or_none()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    printer.is_active = False
    await db.commit()
