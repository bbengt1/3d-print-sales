from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.form_template import FormTemplate


router = APIRouter(prefix="/form-templates", tags=["FormTemplates"])


SCOPES = (
    "invoice",
    "quote",
    "sales_order",
    "purchase_order",
    "bill",
    "expense_claim",
    "journal_entry",
)


class TemplateCreate(BaseModel):
    scope: Literal[
        "invoice",
        "quote",
        "sales_order",
        "purchase_order",
        "bill",
        "expense_claim",
        "journal_entry",
    ]
    name: str = Field(..., min_length=1, max_length=120)
    is_default: bool = False
    defaults: dict[str, Any] = Field(default_factory=dict)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    is_default: bool | None = None
    defaults: dict[str, Any] | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    scope: str
    name: str
    is_default: bool
    defaults: dict[str, Any]
    created_at: datetime.datetime


def _to_resp(t: FormTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=t.id,
        scope=t.scope,
        name=t.name,
        is_default=t.is_default,
        defaults=dict(t.defaults or {}),
        created_at=t.created_at,
    )


@router.get(
    "/{scope}",
    response_model=list[TemplateResponse],
    summary="List form templates for a scope",
)
async def list_templates(scope: str, user: CurrentUser, db: DB):
    if scope not in SCOPES:
        raise HTTPException(status_code=400, detail=f"Unsupported scope {scope!r}")
    rows = (
        await db.execute(
            select(FormTemplate).where(FormTemplate.scope == scope).order_by(FormTemplate.name)
        )
    ).scalars().all()
    return [_to_resp(r) for r in rows]


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a form template",
)
async def create_template(body: TemplateCreate, user: CurrentUser, db: DB):
    # If is_default=True, demote any existing defaults for the scope first
    if body.is_default:
        existing_defaults = (
            await db.execute(
                select(FormTemplate).where(
                    FormTemplate.scope == body.scope, FormTemplate.is_default == True  # noqa: E712
                )
            )
        ).scalars().all()
        for d in existing_defaults:
            d.is_default = False
    t = FormTemplate(
        scope=body.scope,
        name=body.name,
        is_default=body.is_default,
        defaults=body.defaults,
    )
    db.add(t)
    await db.commit()
    return _to_resp(t)


@router.patch(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update a form template",
)
async def update_template(
    template_id: uuid.UUID, body: TemplateUpdate, user: CurrentUser, db: DB
):
    t = (await db.execute(select(FormTemplate).where(FormTemplate.id == template_id))).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found")
    payload = body.model_dump(exclude_unset=True)
    if payload.get("is_default"):
        # Promote — demote others first
        existing = (
            await db.execute(
                select(FormTemplate).where(
                    FormTemplate.scope == t.scope,
                    FormTemplate.is_default == True,  # noqa: E712
                    FormTemplate.id != t.id,
                )
            )
        ).scalars().all()
        for d in existing:
            d.is_default = False
    for k, v in payload.items():
        setattr(t, k, v)
    await db.commit()
    return _to_resp(t)


@router.delete(
    "/{template_id}",
    status_code=204,
    summary="Delete a form template",
)
async def delete_template(template_id: uuid.UUID, user: CurrentUser, db: DB):
    t = (await db.execute(select(FormTemplate).where(FormTemplate.id == template_id))).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(t)
    await db.commit()
