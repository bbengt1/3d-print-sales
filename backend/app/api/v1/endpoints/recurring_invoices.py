from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.recurring_invoice import RecurringInvoice, RecurringInvoiceRun
from app.services.recurring_invoice_service import (
    RecurringInvoiceError,
    run_due,
    run_one,
    skip_next,
)


router = APIRouter(prefix="/recurring-invoices", tags=["RecurringInvoices"])


class TemplateLine(BaseModel):
    description: str
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    notes: str | None = None


class RecurringInvoiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    customer_id: uuid.UUID
    cadence: Literal["daily", "weekly", "monthly", "yearly"] = "monthly"
    interval_count: int = Field(1, gt=0)
    start_on: date
    end_on: date | None = None
    auto_email: bool = False
    line_items_template: list[TemplateLine] = Field(..., min_length=1)
    due_in_days: int = Field(30, gt=0)
    notes: str | None = None


class RecurringInvoiceUpdate(BaseModel):
    name: str | None = None
    cadence: Literal["daily", "weekly", "monthly", "yearly"] | None = None
    interval_count: int | None = Field(None, gt=0)
    end_on: date | None = None
    is_active: bool | None = None
    auto_email: bool | None = None
    line_items_template: list[TemplateLine] | None = None
    due_in_days: int | None = Field(None, gt=0)
    notes: str | None = None


class RecurringInvoiceResponse(BaseModel):
    id: uuid.UUID
    name: str
    customer_id: uuid.UUID
    cadence: str
    interval_count: int
    start_on: date
    next_run_on: date
    last_run_on: date | None
    end_on: date | None
    is_active: bool
    auto_email: bool
    line_items_template: list[dict]
    due_in_days: int
    notes: str | None
    last_error: str | None
    last_failed_at: datetime | None


class RunResponse(BaseModel):
    id: uuid.UUID
    target_date: date
    status: str
    generated_invoice_id: uuid.UUID | None
    error: str | None
    triggered_by: str
    run_at: datetime


def _to_response(r: RecurringInvoice) -> RecurringInvoiceResponse:
    return RecurringInvoiceResponse(
        id=r.id,
        name=r.name,
        customer_id=r.customer_id,
        cadence=r.cadence,
        interval_count=r.interval_count,
        start_on=r.start_on,
        next_run_on=r.next_run_on,
        last_run_on=r.last_run_on,
        end_on=r.end_on,
        is_active=r.is_active,
        auto_email=r.auto_email,
        line_items_template=list(r.line_items_template or []),
        due_in_days=r.due_in_days,
        notes=r.notes,
        last_error=r.last_error,
        last_failed_at=r.last_failed_at,
    )


def _to_run_response(run: RecurringInvoiceRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        target_date=run.target_date,
        status=run.status,
        generated_invoice_id=run.generated_invoice_id,
        error=run.error,
        triggered_by=run.triggered_by,
        run_at=run.run_at,
    )


@router.get("", response_model=list[RecurringInvoiceResponse], summary="List recurring invoices")
async def list_recurring(user: CurrentUser, db: DB, active_only: bool = False):
    stmt = select(RecurringInvoice).order_by(RecurringInvoice.next_run_on)
    if active_only:
        stmt = stmt.where(RecurringInvoice.is_active == True)  # noqa: E712
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("", response_model=RecurringInvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Create a recurring invoice rule")
async def create_recurring(body: RecurringInvoiceCreate, user: CurrentUser, db: DB):
    r = RecurringInvoice(
        name=body.name,
        customer_id=body.customer_id,
        cadence=body.cadence,
        interval_count=body.interval_count,
        start_on=body.start_on,
        next_run_on=body.start_on,
        end_on=body.end_on,
        auto_email=body.auto_email,
        line_items_template=[l.model_dump(mode="json") for l in body.line_items_template],
        due_in_days=body.due_in_days,
        notes=body.notes,
    )
    db.add(r)
    await db.commit()
    return _to_response(r)


@router.get("/{recurring_id}", response_model=RecurringInvoiceResponse, summary="Get recurring invoice")
async def get_recurring(recurring_id: uuid.UUID, user: CurrentUser, db: DB):
    r = (await db.execute(select(RecurringInvoice).where(RecurringInvoice.id == recurring_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    return _to_response(r)


@router.patch("/{recurring_id}", response_model=RecurringInvoiceResponse, summary="Update a recurring invoice")
async def update_recurring(recurring_id: uuid.UUID, body: RecurringInvoiceUpdate, user: CurrentUser, db: DB):
    r = (await db.execute(select(RecurringInvoice).where(RecurringInvoice.id == recurring_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    payload = body.model_dump(exclude_unset=True)
    if "line_items_template" in payload and payload["line_items_template"] is not None:
        payload["line_items_template"] = [l for l in payload["line_items_template"]]
    for k, v in payload.items():
        setattr(r, k, v)
    await db.commit()
    return _to_response(r)


@router.delete("/{recurring_id}", status_code=204, summary="Delete a recurring invoice")
async def delete_recurring(recurring_id: uuid.UUID, user: CurrentUser, db: DB):
    r = (await db.execute(select(RecurringInvoice).where(RecurringInvoice.id == recurring_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    await db.delete(r)
    await db.commit()


@router.post("/{recurring_id}/run-now", response_model=RunResponse, summary="Generate one invoice immediately and advance the schedule")
async def run_now_ep(recurring_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        run = await run_one(db, recurring_id=recurring_id, triggered_by="manual_run_now")
    except RecurringInvoiceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_run_response(run)


@router.post("/{recurring_id}/skip-next", response_model=RunResponse, summary="Advance the schedule without generating an invoice")
async def skip_ep(recurring_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        run = await skip_next(db, recurring_id)
    except RecurringInvoiceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_run_response(run)


@router.post("/run-due", summary="Cron entry point — generate due invoices and advance schedules")
async def run_due_ep(user: CurrentUser, db: DB):
    summary = await run_due(db)
    await db.commit()
    return summary


@router.get("/{recurring_id}/runs", response_model=list[RunResponse], summary="Run history for a recurring invoice")
async def list_runs(recurring_id: uuid.UUID, user: CurrentUser, db: DB):
    rows = (
        await db.execute(
            select(RecurringInvoiceRun)
            .where(RecurringInvoiceRun.recurring_invoice_id == recurring_id)
            .order_by(RecurringInvoiceRun.run_at.desc())
        )
    ).scalars().all()
    return [_to_run_response(r) for r in rows]
