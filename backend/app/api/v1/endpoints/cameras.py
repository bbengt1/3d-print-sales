from __future__ import annotations

import uuid
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.camera import Camera
from app.models.printer import Printer
from app.schemas.camera import (
    CameraCreate,
    CameraResponse,
    CameraUpdate,
    PaginatedCameras,
)

router = APIRouter(prefix="/cameras", tags=["Cameras"])

_SNAPSHOT_TIMEOUT = 5.0


def _prepare_camera_response(camera: Camera, printer_name: str | None = None) -> Camera:
    """Attach computed display fields onto the ORM instance."""
    setattr(camera, "printer_name", printer_name)
    setattr(camera, "snapshot_url", f"/api/v1/cameras/{camera.id}/snapshot")
    base = camera.go2rtc_base_url
    stream = quote(camera.stream_name, safe="")
    # Replace http(s) with ws(s) for the MSE WebSocket URL
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    setattr(camera, "mse_ws_url", f"{ws_base}/api/ws?src={stream}")
    return camera


async def _get_camera_or_404(db: DB, camera_id: uuid.UUID) -> Camera:
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


async def _get_printer_name(db: DB, printer_id: uuid.UUID | None) -> str | None:
    if printer_id is None:
        return None
    result = await db.execute(select(Printer.name).where(Printer.id == printer_id))
    return result.scalar_one_or_none()


async def _validate_printer_assignment(
    db: DB, printer_id: uuid.UUID, exclude_camera_id: uuid.UUID | None = None
) -> None:
    """Ensure the target printer exists and is not already assigned to another camera."""
    printer = await db.execute(select(Printer.id).where(Printer.id == printer_id))
    if printer.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Printer not found")

    stmt = select(Camera.id).where(Camera.printer_id == printer_id, Camera.is_active.is_(True))
    if exclude_camera_id:
        stmt = stmt.where(Camera.id != exclude_camera_id)
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This printer already has a camera assigned")


@router.get(
    "",
    response_model=PaginatedCameras,
    summary="List cameras",
    description="Returns paginated cameras with optional filtering.",
)
async def list_cameras(
    db: DB,
    is_active: bool | None = Query(None, description="Filter by active status"),
    assigned: bool | None = Query(None, description="Filter by printer assignment"),
    search: str | None = Query(None, description="Search by name, slug, or stream name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    base = select(Camera)
    if is_active is not None:
        base = base.where(Camera.is_active == is_active)
    if assigned is True:
        base = base.where(Camera.printer_id.isnot(None))
    elif assigned is False:
        base = base.where(Camera.printer_id.is_(None))
    if search:
        pattern = f"%{search}%"
        base = base.where(
            Camera.name.ilike(pattern) | Camera.slug.ilike(pattern) | Camera.stream_name.ilike(pattern)
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    result = await db.execute(base.order_by(Camera.name).offset(skip).limit(limit))
    items = result.scalars().all()

    # Bulk-fetch printer names
    printer_ids = [c.printer_id for c in items if c.printer_id]
    printer_names: dict[uuid.UUID, str] = {}
    if printer_ids:
        rows = await db.execute(select(Printer.id, Printer.name).where(Printer.id.in_(printer_ids)))
        printer_names = {row.id: row.name for row in rows}

    for camera in items:
        _prepare_camera_response(camera, printer_names.get(camera.printer_id))

    return PaginatedCameras(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Get camera by ID",
)
async def get_camera(camera_id: uuid.UUID, db: DB):
    camera = await _get_camera_or_404(db, camera_id)
    printer_name = await _get_printer_name(db, camera.printer_id)
    return _prepare_camera_response(camera, printer_name)


@router.post(
    "",
    response_model=CameraResponse,
    status_code=201,
    summary="Create a camera",
)
async def create_camera(body: CameraCreate, user: CurrentUser, db: DB):
    existing = await db.execute(
        select(Camera.id).where((Camera.name == body.name) | (Camera.slug == body.slug))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Camera name or slug already exists")

    if body.printer_id:
        await _validate_printer_assignment(db, body.printer_id)

    camera = Camera(**body.model_dump())
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    printer_name = await _get_printer_name(db, camera.printer_id)
    return _prepare_camera_response(camera, printer_name)


@router.put(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Update a camera",
)
async def update_camera(camera_id: uuid.UUID, body: CameraUpdate, user: CurrentUser, db: DB):
    camera = await _get_camera_or_404(db, camera_id)
    update_data = body.model_dump(exclude_unset=True)
    clear_printer_id = update_data.pop("clear_printer_id", False)

    if "name" in update_data or "slug" in update_data:
        existing = await db.execute(
            select(Camera.id).where(
                Camera.id != camera_id,
                (Camera.name == update_data.get("name", camera.name))
                | (Camera.slug == update_data.get("slug", camera.slug)),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Camera name or slug already exists")

    if "printer_id" in update_data and update_data["printer_id"] is not None:
        await _validate_printer_assignment(db, update_data["printer_id"], exclude_camera_id=camera_id)

    for field, value in update_data.items():
        setattr(camera, field, value)

    if clear_printer_id:
        camera.printer_id = None

    await db.commit()
    await db.refresh(camera)
    printer_name = await _get_printer_name(db, camera.printer_id)
    return _prepare_camera_response(camera, printer_name)


@router.delete(
    "/{camera_id}",
    status_code=204,
    summary="Deactivate a camera",
    description="Soft-deletes a camera by setting is_active=false and clearing printer assignment.",
)
async def delete_camera(camera_id: uuid.UUID, user: CurrentUser, db: DB):
    camera = await _get_camera_or_404(db, camera_id)
    camera.is_active = False
    camera.printer_id = None
    await db.commit()


@router.post(
    "/{camera_id}/assign",
    response_model=CameraResponse,
    summary="Assign or unassign a camera to a printer",
)
async def assign_camera(camera_id: uuid.UUID, body: dict, user: CurrentUser, db: DB):
    camera = await _get_camera_or_404(db, camera_id)
    printer_id = body.get("printer_id")

    if printer_id is not None:
        printer_uuid = uuid.UUID(printer_id) if isinstance(printer_id, str) else printer_id
        await _validate_printer_assignment(db, printer_uuid, exclude_camera_id=camera_id)
        camera.printer_id = printer_uuid
    else:
        camera.printer_id = None

    await db.commit()
    await db.refresh(camera)
    printer_name = await _get_printer_name(db, camera.printer_id)
    return _prepare_camera_response(camera, printer_name)


@router.post(
    "/test-snapshot",
    summary="Test camera snapshot by URL",
    description="Proxies a snapshot from go2rtc using provided URL and stream name, for previewing before saving.",
)
async def test_camera_snapshot(body: dict, user: CurrentUser, db: DB):
    base_url = (body.get("go2rtc_base_url") or "").strip().rstrip("/")
    stream_name = (body.get("stream_name") or "").strip()
    if not base_url or not stream_name:
        raise HTTPException(status_code=400, detail="go2rtc_base_url and stream_name are required")

    stream = quote(stream_name, safe="")
    snapshot_url = f"{base_url}/api/frame.jpeg?src={stream}"

    try:
        async with httpx.AsyncClient(timeout=_SNAPSHOT_TIMEOUT) as client:
            resp = await client.get(snapshot_url)
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Snapshot unavailable: {exc}") from exc

    return Response(content=resp.content, media_type="image/jpeg")


@router.get(
    "/{camera_id}/snapshot",
    summary="Get camera snapshot",
    description="Proxies a single MJPEG frame from go2rtc for health checking and CORS-free fallback.",
)
async def get_camera_snapshot(camera_id: uuid.UUID, db: DB):
    camera = await _get_camera_or_404(db, camera_id)
    if not camera.is_active:
        raise HTTPException(status_code=404, detail="Camera is inactive")

    stream = quote(camera.stream_name, safe="")
    snapshot_url = f"{camera.go2rtc_base_url}/api/frame.jpeg?src={stream}"

    try:
        async with httpx.AsyncClient(timeout=_SNAPSHOT_TIMEOUT) as client:
            resp = await client.get(snapshot_url)
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Camera snapshot unavailable: {exc}") from exc

    return Response(content=resp.content, media_type="image/jpeg")
