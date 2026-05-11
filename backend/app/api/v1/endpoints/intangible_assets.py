from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.intangible_asset import AmortizationEntry, IntangibleAsset
from app.services.intangible_asset_service import (
    IntangibleAssetError,
    can_edit_critical_fields,
    compute_book_value,
    dispose_asset,
    planned_schedule,
    post_amortization,
)


router = APIRouter(prefix="/intangible-assets", tags=["IntangibleAssets"])


class IntangibleAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    asset_tag: str | None = Field(None, max_length=120)
    description: str | None = None
    acquired_on: date
    acquisition_cost: Decimal = Field(..., gt=0)
    salvage_value: Decimal = Field(0, ge=0)
    useful_life_months: int = Field(..., gt=0)
    amortization_method: Literal["straight_line", "declining_balance"] = "straight_line"
    declining_balance_rate: Decimal | None = Field(None, gt=0)
    asset_account_id: uuid.UUID | None = None
    accumulated_amortization_account_id: uuid.UUID | None = None
    amortization_expense_account_id: uuid.UUID | None = None
    notes: str | None = None


class IntangibleAssetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    asset_tag: str | None = Field(None, max_length=120)
    description: str | None = None
    acquisition_cost: Decimal | None = Field(None, gt=0)
    salvage_value: Decimal | None = Field(None, ge=0)
    useful_life_months: int | None = Field(None, gt=0)
    amortization_method: Literal["straight_line", "declining_balance"] | None = None
    declining_balance_rate: Decimal | None = Field(None, gt=0)
    notes: str | None = None


class IntangibleAssetResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_tag: str | None
    description: str | None
    acquired_on: date
    acquisition_cost: Decimal
    salvage_value: Decimal
    useful_life_months: int
    amortization_method: str
    declining_balance_rate: Decimal | None
    asset_account_id: uuid.UUID
    accumulated_amortization_account_id: uuid.UUID
    amortization_expense_account_id: uuid.UUID
    status: str
    disposed_on: date | None
    disposal_proceeds: Decimal | None
    disposal_journal_entry_id: uuid.UUID | None
    notes: str | None
    book_value: Decimal


class AmortizationPostRequest(BaseModel):
    period_end: date
    asset_ids: list[uuid.UUID] | None = None


class DisposeRequest(BaseModel):
    disposed_on: date
    proceeds: Decimal | None = Field(None, ge=0)
    proceeds_account_id: uuid.UUID | None = None


class ScheduleRow(BaseModel):
    period_end: date
    amount: Decimal


class IntangibleAssetDetail(IntangibleAssetResponse):
    schedule: list[ScheduleRow]
    posted_periods: list[date]


async def _hydrate(db, asset: IntangibleAsset) -> IntangibleAssetResponse:
    book = await compute_book_value(db, asset.id)
    return IntangibleAssetResponse(
        id=asset.id,
        name=asset.name,
        asset_tag=asset.asset_tag,
        description=asset.description,
        acquired_on=asset.acquired_on,
        acquisition_cost=Decimal(asset.acquisition_cost),
        salvage_value=Decimal(asset.salvage_value),
        useful_life_months=asset.useful_life_months,
        amortization_method=asset.amortization_method,
        declining_balance_rate=Decimal(asset.declining_balance_rate) if asset.declining_balance_rate is not None else None,
        asset_account_id=asset.asset_account_id,
        accumulated_amortization_account_id=asset.accumulated_amortization_account_id,
        amortization_expense_account_id=asset.amortization_expense_account_id,
        status=asset.status,
        disposed_on=asset.disposed_on,
        disposal_proceeds=Decimal(asset.disposal_proceeds) if asset.disposal_proceeds is not None else None,
        disposal_journal_entry_id=asset.disposal_journal_entry_id,
        notes=asset.notes,
        book_value=book,
    )


async def _resolve_default_account(db, code: str) -> uuid.UUID:
    a = (await db.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=400, detail=f"Account with code {code} not found in chart of accounts")
    return a.id


@router.get("", response_model=list[IntangibleAssetResponse], summary="List intangible assets")
async def list_assets(user: CurrentUser, db: DB, status_filter: str | None = None):
    stmt = select(IntangibleAsset).order_by(IntangibleAsset.acquired_on.desc())
    if status_filter:
        stmt = stmt.where(IntangibleAsset.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _hydrate(db, r) for r in rows]


@router.post("", response_model=IntangibleAssetResponse, status_code=status.HTTP_201_CREATED, summary="Register a new intangible asset")
async def create_asset(body: IntangibleAssetCreate, user: CurrentUser, db: DB):
    asset_account_id = body.asset_account_id or await _resolve_default_account(db, "1800")
    accum_id = body.accumulated_amortization_account_id or await _resolve_default_account(db, "1850")
    expense_id = body.amortization_expense_account_id or await _resolve_default_account(db, "6750")
    asset = IntangibleAsset(
        name=body.name,
        asset_tag=body.asset_tag,
        description=body.description,
        acquired_on=body.acquired_on,
        acquisition_cost=body.acquisition_cost,
        salvage_value=body.salvage_value,
        useful_life_months=body.useful_life_months,
        amortization_method=body.amortization_method,
        declining_balance_rate=body.declining_balance_rate,
        asset_account_id=asset_account_id,
        accumulated_amortization_account_id=accum_id,
        amortization_expense_account_id=expense_id,
        notes=body.notes,
    )
    db.add(asset)
    await db.commit()
    return await _hydrate(db, asset)


@router.get("/{asset_id}", response_model=IntangibleAssetDetail, summary="Intangible asset detail with schedule")
async def get_asset(asset_id: uuid.UUID, user: CurrentUser, db: DB):
    asset = (await db.execute(select(IntangibleAsset).where(IntangibleAsset.id == asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Intangible asset not found")
    base = await _hydrate(db, asset)
    schedule = [ScheduleRow(period_end=p, amount=a) for p, a in planned_schedule(asset)]
    posted = [
        e
        for e in (
            await db.execute(
                select(AmortizationEntry.period_end).where(
                    AmortizationEntry.intangible_asset_id == asset.id
                )
            )
        ).scalars().all()
    ]
    return IntangibleAssetDetail(**base.model_dump(), schedule=schedule, posted_periods=posted)


@router.patch("/{asset_id}", response_model=IntangibleAssetResponse, summary="Update an intangible asset")
async def update_asset(asset_id: uuid.UUID, body: IntangibleAssetUpdate, user: CurrentUser, db: DB):
    asset = (await db.execute(select(IntangibleAsset).where(IntangibleAsset.id == asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Intangible asset not found")
    if asset.status == "disposed":
        raise HTTPException(status_code=400, detail="Cannot edit a disposed asset")

    critical_locked = not await can_edit_critical_fields(db, asset.id)
    payload = body.model_dump(exclude_unset=True)
    if critical_locked:
        for k in ("acquisition_cost", "salvage_value", "useful_life_months", "amortization_method", "declining_balance_rate"):
            if k in payload:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot edit '{k}' once amortization has been posted",
                )
    for k, v in payload.items():
        setattr(asset, k, v)
    await db.commit()
    return await _hydrate(db, asset)


@router.post("/post-amortization", summary="Post amortization through a period for selected (or all active) assets")
async def post_amort(body: AmortizationPostRequest, user: CurrentUser, db: DB):
    if body.asset_ids:
        assets = (
            await db.execute(select(IntangibleAsset).where(IntangibleAsset.id.in_(body.asset_ids)))
        ).scalars().all()
    else:
        assets = (
            await db.execute(select(IntangibleAsset).where(IntangibleAsset.status == "active"))
        ).scalars().all()

    # #279 Codex P1: `post_amortization` calls `create_journal_entry`, which
    # commits internally. If we just looped and let a later asset raise, any
    # earlier asset's JEs would already be persisted — partial bulk postings
    # are unsafe for retries and reconciliation. Pre-validate every asset's
    # plan against closed periods / disposal status before any writes, so a
    # request either posts every asset's pending months or none of them.
    for a in assets:
        if a.status == "disposed":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot post amortization on a disposed asset ({a.name})",
            )
        posted_periods = set(
            (
                await db.execute(
                    select(AmortizationEntry.period_end).where(
                        AmortizationEntry.intangible_asset_id == a.id
                    )
                )
            ).scalars().all()
        )
        for period_end, amount in planned_schedule(a):
            if period_end > body.period_end:
                break
            if period_end in posted_periods or amount <= 0:
                continue
            period_row = (
                await db.execute(
                    select(AccountingPeriod).where(
                        AccountingPeriod.start_date <= period_end,
                        AccountingPeriod.end_date >= period_end,
                    )
                )
            ).scalar_one_or_none()
            if period_row is not None and period_row.status != "open":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Accounting period containing {period_end.isoformat()} "
                        f"is closed (asset '{a.name}')"
                    ),
                )

    posted_count = 0
    for a in assets:
        try:
            new_entries = await post_amortization(db, asset_id=a.id, through=body.period_end)
            posted_count += len(new_entries)
        except IntangibleAssetError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {"posted_count": posted_count, "asset_count": len(assets)}


@router.post("/{asset_id}/dispose", response_model=IntangibleAssetResponse, summary="Dispose an intangible asset")
async def dispose(asset_id: uuid.UUID, body: DisposeRequest, user: CurrentUser, db: DB):
    gain_id = await _resolve_default_account(db, "4920")
    loss_id = await _resolve_default_account(db, "6760")
    try:
        asset = await dispose_asset(
            db,
            asset_id=asset_id,
            disposed_on=body.disposed_on,
            proceeds=body.proceeds,
            proceeds_account_id=body.proceeds_account_id,
            gain_account_id=gain_id,
            loss_account_id=loss_id,
        )
    except IntangibleAssetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, asset)


@router.delete("/{asset_id}", status_code=204, summary="Delete an intangible asset (only if no entries and not disposed)")
async def delete_asset(asset_id: uuid.UUID, user: CurrentUser, db: DB):
    asset = (await db.execute(select(IntangibleAsset).where(IntangibleAsset.id == asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Intangible asset not found")
    if not await can_edit_critical_fields(db, asset.id):
        raise HTTPException(status_code=400, detail="Cannot delete an asset with amortization entries")
    if asset.status == "disposed":
        raise HTTPException(status_code=400, detail="Cannot delete a disposed asset")
    await db.delete(asset)
    await db.commit()
