from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.printer import Printer
from app.schemas.printer import (
    PaginatedPrinters,
    PrinterConnectionTestResponse,
    PrinterCreate,
    PrinterResponse,
    PrinterUpdate,
)
from app.services.printer_monitoring import (
    MoonrakerMonitorProvider,
    PrinterMonitoringError,
    mark_printer_stale_if_needed,
    refresh_printer_monitoring,
    test_printer_connection,
)

router = APIRouter(prefix="/printers", tags=["Printers"])


def _apply_thumbnail_urls(printer: Printer) -> Printer:
    thumbnail_path = getattr(printer, "current_print_thumbnail_path", None)
    setattr(printer, "current_print_thumbnail_url", f"/api/v1/printers/{printer.id}/thumbnail" if thumbnail_path else None)
    if getattr(printer, "current_print_thumbnails", None) is None:
        setattr(printer, "current_print_thumbnails", [])
    return printer


async def _get_printer_or_404(db: DB, printer_id: uuid.UUID) -> Printer:
    result = await db.execute(select(Printer).where(Printer.id == printer_id))
    printer = result.scalar_one_or_none()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


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
    for printer in items:
        mark_printer_stale_if_needed(printer)
        await refresh_printer_monitoring(db, printer)
        _apply_thumbnail_urls(printer)
    return PaginatedPrinters(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{printer_id}",
    response_model=PrinterResponse,
    summary="Get printer by ID",
    description="Retrieve a single printer record.",
)
async def get_printer(printer_id: uuid.UUID, db: DB):
    printer = await _get_printer_or_404(db, printer_id)
    mark_printer_stale_if_needed(printer)
    await refresh_printer_monitoring(db, printer)
    return _apply_thumbnail_urls(printer)


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
    if printer.monitor_enabled:
        await refresh_printer_monitoring(db, printer, force=True)
    return _apply_thumbnail_urls(printer)


@router.put(
    "/{printer_id}",
    response_model=PrinterResponse,
    summary="Update a printer",
    description="Update one or more fields of a printer.",
)
async def update_printer(printer_id: uuid.UUID, body: PrinterUpdate, user: CurrentUser, db: DB):
    printer = await _get_printer_or_404(db, printer_id)

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

    if not printer.monitor_enabled:
        printer.monitor_online = None
        printer.monitor_status = None
        printer.monitor_progress_percent = None
        printer.current_print_name = None
        setattr(printer, "current_print_thumbnail_path", None)
        setattr(printer, "current_print_thumbnail_url", None)
        setattr(printer, "current_print_thumbnails", [])
        printer.monitor_last_message = None
        printer.monitor_last_error = None
        printer.monitor_bed_temp_c = None
        printer.monitor_tool_temp_c = None
        printer.monitor_bed_target_c = None
        printer.monitor_tool_target_c = None
        printer.monitor_current_layer = None
        printer.monitor_total_layers = None
        printer.monitor_elapsed_seconds = None
        printer.monitor_remaining_seconds = None
        printer.monitor_eta_at = None
        printer.monitor_last_event_type = None
        printer.monitor_last_event_at = None
        printer.monitor_ws_connected = None
        printer.monitor_ws_last_error = None
        printer.monitor_last_seen_at = None
        printer.monitor_last_updated_at = None

    await db.commit()
    await db.refresh(printer)
    if printer.monitor_enabled:
        await refresh_printer_monitoring(db, printer, force=True)
    return _apply_thumbnail_urls(printer)


@router.post(
    "/{printer_id}/refresh",
    response_model=PrinterResponse,
    summary="Refresh live printer status",
    description="Force a live provider refresh for a configured printer.",
)
async def refresh_printer(printer_id: uuid.UUID, user: CurrentUser, db: DB):
    printer = await _get_printer_or_404(db, printer_id)
    await refresh_printer_monitoring(db, printer, force=True)
    return _apply_thumbnail_urls(printer)


@router.post(
    "/{printer_id}/test-connection",
    response_model=PrinterConnectionTestResponse,
    summary="Test printer monitoring connection",
    description="Tests connectivity to the configured monitoring provider without changing saved live state.",
)
async def test_connection(printer_id: uuid.UUID, user: CurrentUser, db: DB):
    printer = await _get_printer_or_404(db, printer_id)
    try:
        result = await test_printer_connection(printer)
        return PrinterConnectionTestResponse(
            ok=result.ok,
            provider=result.provider,
            normalized_status=result.normalized_status,
            online=result.online,
            message=result.message,
        )
    except PrinterMonitoringError as exc:
        return PrinterConnectionTestResponse(ok=False, provider=printer.monitor_provider or "unconfigured", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        return PrinterConnectionTestResponse(ok=False, provider=printer.monitor_provider or "unconfigured", message=str(exc))


@router.delete(
    "/{printer_id}",
    status_code=204,
    summary="Deactivate a printer",
    description="Soft-deletes a printer by setting is_active=false.",
)
async def delete_printer(printer_id: uuid.UUID, user: CurrentUser, db: DB):
    printer = await _get_printer_or_404(db, printer_id)
    printer.is_active = False
    await db.commit()


@router.get(
    "/{printer_id}/thumbnail",
    summary="Get current print thumbnail",
    description="Fetches the active Moonraker print thumbnail through the backend to avoid frontend CORS and path encoding issues.",
)
async def get_printer_thumbnail(printer_id: uuid.UUID, db: DB):
    printer = await _get_printer_or_404(db, printer_id)
    if not printer.monitor_enabled or printer.monitor_provider != "moonraker":
        raise HTTPException(status_code=404, detail="Printer thumbnail unavailable")

    provider = MoonrakerMonitorProvider()
    try:
        thumbnail = await provider.fetch_current_thumbnail(printer)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if thumbnail is None:
        raise HTTPException(status_code=404, detail="Printer thumbnail unavailable")

    return Response(content=thumbnail.content, media_type=thumbnail.media_type)
