from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, CurrentAdmin
from app.schemas.setting import BulkSettingUpdate, SettingResponse, SettingUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get(
    "",
    response_model=list[SettingResponse],
    summary="List all settings",
    description="Returns every business configuration setting (currency, margins, fees, etc.).",
)
async def list_settings(db: DB):
    from app.models.setting import Setting

    result = await db.execute(select(Setting).order_by(Setting.key))
    return result.scalars().all()


@router.get(
    "/{key}",
    response_model=SettingResponse,
    summary="Get a setting by key",
    description="Retrieve a single configuration setting by its unique key.",
)
async def get_setting(key: str, db: DB):
    from app.models.setting import Setting

    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting


@router.put(
    "/{key}",
    response_model=SettingResponse,
    summary="Update a setting",
    description="Update the value of an existing configuration setting.",
)
async def update_setting(key: str, body: SettingUpdate, admin: CurrentAdmin, db: DB):
    from app.models.setting import Setting

    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    setting.value = body.value
    await db.commit()
    await db.refresh(setting)
    return setting


@router.put(
    "/bulk",
    response_model=list[SettingResponse],
    summary="Bulk update settings",
    description="Update multiple settings in a single request. Keys that don't exist are silently skipped.",
)
async def bulk_update_settings(body: BulkSettingUpdate, admin: CurrentAdmin, db: DB):
    from app.models.setting import Setting

    updated = []
    for key, value in body.settings.items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
            updated.append(setting)
    await db.commit()
    return updated
