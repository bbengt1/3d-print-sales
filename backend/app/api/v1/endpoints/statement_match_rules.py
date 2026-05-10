from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.statement_match_rule import StatementMatchRule
from app.services.statement_match_rule_service import (
    StatementMatchRuleError,
    apply_rules_to_import,
    create_rule_from_line,
    preview_rules_for_import,
    validate_rule,
)


router = APIRouter(prefix="/banking/rules", tags=["Banking"])


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    account_id: uuid.UUID | None = None
    match_type: Literal["contains", "regex"]
    match_pattern: str = Field(..., min_length=1, max_length=500)
    match_amount_sign: Literal["debit", "credit", "any"] = "any"
    action: Literal["ignore", "create_journal_entry"] = "ignore"
    category_account_id: uuid.UUID | None = None
    counterparty_name: str | None = Field(None, max_length=200)
    priority: int = Field(100, ge=0)
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    account_id: uuid.UUID | None = None
    match_type: Literal["contains", "regex"] | None = None
    match_pattern: str | None = Field(None, max_length=500)
    match_amount_sign: Literal["debit", "credit", "any"] | None = None
    action: Literal["ignore", "create_journal_entry"] | None = None
    category_account_id: uuid.UUID | None = None
    counterparty_name: str | None = None
    priority: int | None = Field(None, ge=0)
    is_active: bool | None = None


class RuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    account_id: uuid.UUID | None
    match_type: str
    match_pattern: str
    match_amount_sign: str
    action: str
    category_account_id: uuid.UUID | None = None
    counterparty_name: str | None = None
    priority: int
    is_active: bool
    created_at: datetime


def _to_response(r: StatementMatchRule) -> RuleResponse:
    return RuleResponse(
        id=r.id,
        name=r.name,
        account_id=r.account_id,
        match_type=r.match_type,
        match_pattern=r.match_pattern,
        match_amount_sign=r.match_amount_sign,
        action=r.action,
        category_account_id=r.category_account_id,
        counterparty_name=r.counterparty_name,
        priority=r.priority,
        is_active=r.is_active,
        created_at=r.created_at,
    )


@router.get("", response_model=list[RuleResponse], summary="List statement-match rules")
async def list_rules(user: CurrentUser, db: DB):
    rows = (
        await db.execute(select(StatementMatchRule).order_by(StatementMatchRule.priority))
    ).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED, summary="Create a rule")
async def create_rule_ep(body: RuleCreate, user: CurrentUser, db: DB):
    try:
        validate_rule(
            match_type=body.match_type,
            match_pattern=body.match_pattern,
            match_amount_sign=body.match_amount_sign,
            action=body.action,
        )
    except StatementMatchRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    r = StatementMatchRule(
        name=body.name,
        account_id=body.account_id,
        match_type=body.match_type,
        match_pattern=body.match_pattern,
        match_amount_sign=body.match_amount_sign,
        action=body.action,
        category_account_id=body.category_account_id,
        counterparty_name=body.counterparty_name,
        priority=body.priority,
        is_active=body.is_active,
    )
    db.add(r)
    await db.commit()
    return _to_response(r)


@router.patch("/{rule_id}", response_model=RuleResponse, summary="Update a rule")
async def update_rule_ep(rule_id: uuid.UUID, body: RuleUpdate, user: CurrentUser, db: DB):
    r = (await db.execute(select(StatementMatchRule).where(StatementMatchRule.id == rule_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(r, k, v)
    try:
        validate_rule(
            match_type=r.match_type,
            match_pattern=r.match_pattern,
            match_amount_sign=r.match_amount_sign,
            action=r.action,
        )
    except StatementMatchRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(r)


@router.delete("/{rule_id}", status_code=204, summary="Delete a rule")
async def delete_rule_ep(rule_id: uuid.UUID, user: CurrentUser, db: DB):
    r = (await db.execute(select(StatementMatchRule).where(StatementMatchRule.id == rule_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(r)
    await db.commit()


@router.post("/imports/{import_id}/apply-rules", summary="Re-apply rules to an existing import's pending lines")
async def apply_rules_ep(import_id: uuid.UUID, user: CurrentUser, db: DB):
    summary = await apply_rules_to_import(db, import_id=import_id)
    await db.commit()
    return summary


@router.get(
    "/imports/{import_id}/preview",
    summary="#316 P2: dry-run preview of which rules would fire on each pending line",
)
async def preview_rules_ep(import_id: uuid.UUID, user: CurrentUser, db: DB):
    return await preview_rules_for_import(db, import_id=import_id)


class CreateFromLineBody(BaseModel):
    statement_line_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=120)
    action: Literal["ignore", "create_journal_entry"] = "ignore"
    category_account_id: uuid.UUID | None = None


@router.post(
    "/from-line",
    response_model=RuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="#316 P2: create a starter rule derived from a staged statement line",
)
async def create_from_line_ep(body: CreateFromLineBody, user: CurrentUser, db: DB):
    try:
        rule = await create_rule_from_line(
            db,
            statement_line_id=body.statement_line_id,
            name=body.name,
            action=body.action,
            category_account_id=body.category_account_id,
        )
    except StatementMatchRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_response(rule)
