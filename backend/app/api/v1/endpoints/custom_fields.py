from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.custom_field import CustomFieldDefinition
from app.services.custom_field_service import (
    CustomFieldError,
    list_definitions,
    read_values,
    upsert_values,
    validate_definition,
)


router = APIRouter(prefix="/custom-fields", tags=["CustomFields"])


class DefinitionCreate(BaseModel):
    scope: str = Field(..., min_length=1, max_length=40)
    key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    field_type: Literal["text", "long_text", "number", "date", "dropdown", "checkbox"]
    options: list[str] | None = None
    is_required: bool = False
    sort_order: int = 100


class DefinitionUpdate(BaseModel):
    name: str | None = None
    options: list[str] | None = None
    is_required: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class DefinitionResponse(BaseModel):
    id: uuid.UUID
    scope: str
    key: str
    name: str
    field_type: str
    options: list[str] | None
    is_required: bool
    sort_order: int
    is_active: bool


def _to_response(d: CustomFieldDefinition) -> DefinitionResponse:
    return DefinitionResponse(
        id=d.id,
        scope=d.scope,
        key=d.key,
        name=d.name,
        field_type=d.field_type,
        options=list(d.options) if d.options else None,
        is_required=d.is_required,
        sort_order=d.sort_order,
        is_active=d.is_active,
    )


@router.get("/{scope}", response_model=list[DefinitionResponse], summary="List custom field definitions for a scope")
async def list_defs_ep(scope: str, user: CurrentUser, db: DB, include_inactive: bool = False):
    try:
        rows = await list_definitions(db, scope=scope, include_inactive=include_inactive)
    except CustomFieldError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return [_to_response(r) for r in rows]


@router.post("", response_model=DefinitionResponse, status_code=status.HTTP_201_CREATED, summary="Create a custom field definition")
async def create_def(body: DefinitionCreate, user: CurrentUser, db: DB):
    try:
        validate_definition(
            scope=body.scope, key=body.key, field_type=body.field_type, options=body.options,
        )
    except CustomFieldError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Unique on (scope, key)
    existing = (
        await db.execute(
            select(CustomFieldDefinition).where(
                CustomFieldDefinition.scope == body.scope,
                CustomFieldDefinition.key == body.key,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Custom field {body.scope}.{body.key} already exists")

    d = CustomFieldDefinition(
        scope=body.scope,
        key=body.key,
        name=body.name,
        field_type=body.field_type,
        options=body.options,
        is_required=body.is_required,
        sort_order=body.sort_order,
    )
    db.add(d)
    await db.commit()
    return _to_response(d)


@router.patch("/{def_id}", response_model=DefinitionResponse, summary="Update a definition (cannot change field_type or scope)")
async def update_def(def_id: uuid.UUID, body: DefinitionUpdate, user: CurrentUser, db: DB):
    d = (await db.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == def_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Definition not found")
    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(d, k, v)
    # Re-validate dropdown options if they changed
    if "options" in payload and d.field_type == "dropdown":
        try:
            validate_definition(scope=d.scope, key=d.key, field_type=d.field_type, options=d.options)
        except CustomFieldError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(d)


@router.delete("/{def_id}", status_code=204, summary="Soft-deactivate a definition (values preserved)")
async def deactivate_def(def_id: uuid.UUID, user: CurrentUser, db: DB):
    """Phase 1: deactivate rather than hard-delete so existing values aren't
    silently dropped. Hard delete is a follow-up gated on no-values check.
    """
    d = (await db.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == def_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Definition not found")
    d.is_active = False
    await db.commit()


# ---------- values ----------


class ValueUpsert(BaseModel):
    values: dict[str, Any]


@router.get("/values/{scope}/{record_id}", summary="Read all custom-field values for a record")
async def get_values(scope: str, record_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        return await read_values(db, scope=scope, record_id=record_id)
    except CustomFieldError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/values/{scope}/{record_id}", summary="Set custom-field values for a record")
async def set_values(scope: str, record_id: uuid.UUID, body: ValueUpsert, user: CurrentUser, db: DB):
    try:
        result = await upsert_values(db, scope=scope, record_id=record_id, values=body.values)
    except CustomFieldError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result
