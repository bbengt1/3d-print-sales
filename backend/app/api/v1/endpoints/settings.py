from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB
from app.models.setting import Setting

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingResponse(BaseModel):
    key: str
    value: str
    notes: str | None = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str


class BulkSettingUpdate(BaseModel):
    settings: dict[str, str]


@router.get("", response_model=list[SettingResponse])
async def list_settings(db: DB):
    result = await db.execute(select(Setting).order_by(Setting.key))
    return result.scalars().all()


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(key: str, db: DB):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(key: str, body: SettingUpdate, db: DB):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    setting.value = body.value
    await db.commit()
    await db.refresh(setting)
    return setting


@router.put("/bulk", response_model=list[SettingResponse])
async def bulk_update_settings(body: BulkSettingUpdate, db: DB):
    updated = []
    for key, value in body.settings.items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
            updated.append(setting)
    await db.commit()
    return updated
