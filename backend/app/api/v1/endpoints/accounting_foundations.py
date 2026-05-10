from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import csv
import io

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.recurring_journal_entry import RecurringJournalEntry, RecurringJournalEntryRun
from app.services.accounting_foundations_service import (
    AccountingFoundationsError,
    post_starting_balances,
    run_due_jes,
    run_one_je,
    skip_next_je,
    suspense_report,
)


router = APIRouter(prefix="/accounting", tags=["AccountingFoundations"])


# ---------- recurring JE schemas ----------


class TemplateLine(BaseModel):
    account_id: uuid.UUID
    entry_type: Literal["debit", "credit"]
    amount: Decimal = Field(..., gt=0)
    description: str | None = None


class RJECreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    cadence: Literal["daily", "weekly", "monthly", "yearly"] = "monthly"
    interval_count: int = Field(1, gt=0)
    start_on: date
    end_on: date | None = None
    memo: str | None = None
    lines_template: list[TemplateLine] = Field(..., min_length=2)


class RJEUpdate(BaseModel):
    name: str | None = None
    cadence: Literal["daily", "weekly", "monthly", "yearly"] | None = None
    interval_count: int | None = Field(None, gt=0)
    end_on: date | None = None
    is_active: bool | None = None
    memo: str | None = None
    lines_template: list[TemplateLine] | None = None


class RJEResponse(BaseModel):
    id: uuid.UUID
    name: str
    cadence: str
    interval_count: int
    start_on: date
    next_run_on: date
    last_run_on: date | None
    end_on: date | None
    is_active: bool
    memo: str | None
    lines_template: list[dict]
    last_error: str | None
    last_failed_at: datetime | None


class RunResponse(BaseModel):
    id: uuid.UUID
    target_date: date
    status: str
    generated_journal_entry_id: uuid.UUID | None
    error: str | None
    triggered_by: str
    run_at: datetime


def _to_rje(r: RecurringJournalEntry) -> RJEResponse:
    return RJEResponse(
        id=r.id,
        name=r.name,
        cadence=r.cadence,
        interval_count=r.interval_count,
        start_on=r.start_on,
        next_run_on=r.next_run_on,
        last_run_on=r.last_run_on,
        end_on=r.end_on,
        is_active=r.is_active,
        memo=r.memo,
        lines_template=list(r.lines_template or []),
        last_error=r.last_error,
        last_failed_at=r.last_failed_at,
    )


def _to_run(run: RecurringJournalEntryRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        target_date=run.target_date,
        status=run.status,
        generated_journal_entry_id=run.generated_journal_entry_id,
        error=run.error,
        triggered_by=run.triggered_by,
        run_at=run.run_at,
    )


# ---------- recurring JE endpoints ----------


@router.get("/recurring-journal-entries", response_model=list[RJEResponse], summary="List recurring JEs")
async def list_rjes(user: CurrentUser, db: DB):
    rows = (
        await db.execute(select(RecurringJournalEntry).order_by(RecurringJournalEntry.next_run_on))
    ).scalars().all()
    return [_to_rje(r) for r in rows]


@router.post(
    "/recurring-journal-entries",
    response_model=RJEResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recurring JE",
)
async def create_rje(body: RJECreate, user: CurrentUser, db: DB):
    debit_total = sum((l.amount for l in body.lines_template if l.entry_type == "debit"), Decimal("0"))
    credit_total = sum((l.amount for l in body.lines_template if l.entry_type == "credit"), Decimal("0"))
    if debit_total != credit_total:
        raise HTTPException(status_code=400, detail="Template debits must equal credits")
    r = RecurringJournalEntry(
        name=body.name,
        cadence=body.cadence,
        interval_count=body.interval_count,
        start_on=body.start_on,
        next_run_on=body.start_on,
        end_on=body.end_on,
        memo=body.memo,
        lines_template=[l.model_dump(mode="json") for l in body.lines_template],
    )
    db.add(r)
    await db.commit()
    return _to_rje(r)


@router.patch("/recurring-journal-entries/{rje_id}", response_model=RJEResponse, summary="Update recurring JE")
async def update_rje(rje_id: uuid.UUID, body: RJEUpdate, user: CurrentUser, db: DB):
    r = (await db.execute(select(RecurringJournalEntry).where(RecurringJournalEntry.id == rje_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring JE not found")
    payload = body.model_dump(exclude_unset=True)
    if "lines_template" in payload and payload["lines_template"] is not None:
        debit_total = sum((Decimal(str(l["amount"])) for l in payload["lines_template"] if l["entry_type"] == "debit"), Decimal("0"))
        credit_total = sum((Decimal(str(l["amount"])) for l in payload["lines_template"] if l["entry_type"] == "credit"), Decimal("0"))
        if debit_total != credit_total:
            raise HTTPException(status_code=400, detail="Template debits must equal credits")
    for k, v in payload.items():
        setattr(r, k, v)
    await db.commit()
    return _to_rje(r)


@router.delete("/recurring-journal-entries/{rje_id}", status_code=204, summary="Delete recurring JE")
async def delete_rje(rje_id: uuid.UUID, user: CurrentUser, db: DB):
    r = (await db.execute(select(RecurringJournalEntry).where(RecurringJournalEntry.id == rje_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Recurring JE not found")
    await db.delete(r)
    await db.commit()


@router.post("/recurring-journal-entries/{rje_id}/run-now", response_model=RunResponse, summary="Generate one JE now")
async def run_now_rje(rje_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        run = await run_one_je(db, recurring_id=rje_id)
    except AccountingFoundationsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_run(run)


@router.post("/recurring-journal-entries/{rje_id}/skip-next", response_model=RunResponse, summary="Skip next run")
async def skip_next_rje(rje_id: uuid.UUID, user: CurrentUser, db: DB):
    try:
        run = await skip_next_je(db, rje_id)
    except AccountingFoundationsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return _to_run(run)


@router.post("/recurring-journal-entries/run-due", summary="Cron entry point")
async def run_due_rje(user: CurrentUser, db: DB):
    summary = await run_due_jes(db)
    await db.commit()
    return summary


# ---------- suspense ----------


@router.get("/suspense", summary="List open Suspense (1900) journal lines for reclassification")
async def get_suspense(user: CurrentUser, db: DB):
    return await suspense_report(db)


# ---------- starting balances ----------


class StartingBalanceLine(BaseModel):
    account_id: uuid.UUID
    amount: Decimal


class StartingBalancesRequest(BaseModel):
    as_of: date
    balances: list[StartingBalanceLine] = Field(..., min_length=1)
    force: bool = False


@router.post("/starting-balances", summary="Admin one-shot: post opening balances JE balanced against OBE (3300)")
async def post_starting_balances_ep(body: StartingBalancesRequest, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    try:
        je = await post_starting_balances(
            db,
            as_of=body.as_of,
            balances=[b.model_dump() for b in body.balances],
            force=body.force,
        )
    except AccountingFoundationsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {"journal_entry_id": str(je.id), "entry_number": je.entry_number}


@router.post(
    "/starting-balances.csv",
    summary="#330 P2: Post opening balances from a CSV (account_code,amount[,as_of])",
)
async def post_starting_balances_csv(
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
    as_of: date | None = None,
    force: bool = False,
):
    """Accepts a CSV with header row `account_code,amount` (and optional
    `as_of` column to override the request param). Resolves account codes to
    IDs server-side, then forwards to the same posting service as the JSON
    endpoint, so the JE shape matches.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "account_code" not in reader.fieldnames or "amount" not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="CSV must include 'account_code' and 'amount' columns",
        )
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV had no data rows")

    from app.models.account import Account

    codes = sorted({(r.get("account_code") or "").strip() for r in rows if r.get("account_code")})
    accounts = (
        await db.execute(select(Account).where(Account.code.in_(codes)))
    ).scalars().all()
    by_code = {a.code: a for a in accounts}
    missing = [c for c in codes if c not in by_code]
    if missing:
        raise HTTPException(
            status_code=400, detail=f"Unknown account codes: {', '.join(missing)}"
        )

    target_as_of = as_of
    balances: list[dict] = []
    for r in rows:
        code = (r.get("account_code") or "").strip()
        if not code:
            continue
        try:
            amt = Decimal(str(r.get("amount") or "0").strip())
        except Exception:
            raise HTTPException(
                status_code=400, detail=f"Invalid amount for {code}: {r.get('amount')!r}"
            )
        if target_as_of is None and r.get("as_of"):
            target_as_of = date.fromisoformat(r["as_of"].strip())
        balances.append({"account_id": by_code[code].id, "amount": amt})

    if target_as_of is None:
        raise HTTPException(
            status_code=400,
            detail="`as_of` query param or `as_of` CSV column required",
        )

    try:
        je = await post_starting_balances(
            db, as_of=target_as_of, balances=balances, force=force
        )
    except AccountingFoundationsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {
        "journal_entry_id": str(je.id),
        "entry_number": je.entry_number,
        "rows_processed": len(balances),
    }


# ---------- #330 P2: suspense reclassify inline ----------


class SuspenseReclassifyRequest(BaseModel):
    journal_line_id: uuid.UUID
    target_account_id: uuid.UUID
    posted_on: date
    description: str | None = None


@router.post(
    "/suspense/reclassify",
    summary="#330 P2: Reclassify a Suspense (1900) line by posting an offsetting JE",
)
async def reclassify_suspense_line(
    body: SuspenseReclassifyRequest, user: CurrentUser, db: DB
):
    """Closes out a Suspense line by posting a balanced JE: offset the
    suspense leg and post the same amount to the chosen target account.
    Original line stays put for audit; this is additive.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")

    from app.models.account import Account
    from app.models.journal_line import JournalLine
    from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
    from app.services.accounting_service import create_journal_entry

    line = (
        await db.execute(select(JournalLine).where(JournalLine.id == body.journal_line_id))
    ).scalar_one_or_none()
    if line is None:
        raise HTTPException(status_code=404, detail="Suspense line not found")

    suspense = (
        await db.execute(select(Account).where(Account.code == "1900"))
    ).scalar_one_or_none()
    if suspense is None or line.account_id != suspense.id:
        raise HTTPException(
            status_code=400, detail="Source line does not target Suspense (1900)"
        )

    target = (
        await db.execute(select(Account).where(Account.id == body.target_account_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Target account not found")

    # Post the inverse: if suspense was credited originally, debit it now (and credit target).
    suspense_offset = "debit" if line.entry_type == "credit" else "credit"
    target_side = "credit" if suspense_offset == "debit" else "debit"
    amount = Decimal(line.amount)

    try:
        je = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=body.posted_on,
                memo=body.description or f"Reclassify suspense → {target.code} {target.name}",
                lines=[
                    JournalLineCreate(
                        account_id=suspense.id,
                        entry_type=suspense_offset,
                        amount=amount,
                        description="Suspense reclassify offset",
                    ),
                    JournalLineCreate(
                        account_id=target.id,
                        entry_type=target_side,
                        amount=amount,
                        description=body.description or "Suspense reclassify target",
                    ),
                ],
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {"journal_entry_id": str(je.id), "entry_number": je.entry_number}
