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
from app.models.fixed_asset import DepreciationEntry, FixedAsset
from app.services.fixed_asset_service import (
    FixedAssetError,
    can_edit_critical_fields,
    compute_book_value,
    dispose_asset,
    planned_schedule,
    post_depreciation,
)


router = APIRouter(prefix="/fixed-assets", tags=["FixedAssets"])


# ---------- schemas ----------


class FixedAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    asset_tag: str | None = Field(None, max_length=120)
    description: str | None = None
    acquired_on: date
    acquisition_cost: Decimal = Field(..., gt=0)
    salvage_value: Decimal = Field(0, ge=0)
    useful_life_months: int = Field(..., gt=0)
    depreciation_method: Literal["straight_line", "declining_balance"] = "straight_line"
    declining_balance_rate: Decimal | None = Field(None, gt=0)
    asset_account_id: uuid.UUID | None = None
    accumulated_depreciation_account_id: uuid.UUID | None = None
    depreciation_expense_account_id: uuid.UUID | None = None
    acquisition_bill_id: uuid.UUID | None = None
    notes: str | None = None


class FixedAssetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    asset_tag: str | None = Field(None, max_length=120)
    description: str | None = None
    acquisition_cost: Decimal | None = Field(None, gt=0)
    salvage_value: Decimal | None = Field(None, ge=0)
    useful_life_months: int | None = Field(None, gt=0)
    depreciation_method: Literal["straight_line", "declining_balance"] | None = None
    declining_balance_rate: Decimal | None = Field(None, gt=0)
    notes: str | None = None


class FixedAssetResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_tag: str | None
    description: str | None
    acquired_on: date
    acquisition_cost: Decimal
    salvage_value: Decimal
    useful_life_months: int
    depreciation_method: str
    declining_balance_rate: Decimal | None
    asset_account_id: uuid.UUID
    accumulated_depreciation_account_id: uuid.UUID
    depreciation_expense_account_id: uuid.UUID
    status: str
    disposed_on: date | None
    disposal_proceeds: Decimal | None
    disposal_journal_entry_id: uuid.UUID | None
    notes: str | None
    book_value: Decimal


class DepreciationPostRequest(BaseModel):
    period_end: date
    asset_ids: list[uuid.UUID] | None = None


class DisposeRequest(BaseModel):
    disposed_on: date
    proceeds: Decimal | None = Field(None, ge=0)
    proceeds_account_id: uuid.UUID | None = None


class ScheduleRow(BaseModel):
    period_end: date
    amount: Decimal


class FixedAssetDetail(FixedAssetResponse):
    schedule: list[ScheduleRow]
    posted_periods: list[date]


# ---------- helpers ----------


async def _hydrate(db, asset: FixedAsset) -> FixedAssetResponse:
    book = await compute_book_value(db, asset.id)
    return FixedAssetResponse(
        id=asset.id,
        name=asset.name,
        asset_tag=asset.asset_tag,
        description=asset.description,
        acquired_on=asset.acquired_on,
        acquisition_cost=Decimal(asset.acquisition_cost),
        salvage_value=Decimal(asset.salvage_value),
        useful_life_months=asset.useful_life_months,
        depreciation_method=asset.depreciation_method,
        declining_balance_rate=Decimal(asset.declining_balance_rate) if asset.declining_balance_rate is not None else None,
        asset_account_id=asset.asset_account_id,
        accumulated_depreciation_account_id=asset.accumulated_depreciation_account_id,
        depreciation_expense_account_id=asset.depreciation_expense_account_id,
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
        raise HTTPException(
            status_code=400,
            detail=f"Account with code {code} not found in chart of accounts; seed it first.",
        )
    return a.id


# ---------- endpoints ----------


@router.get("", response_model=list[FixedAssetResponse], summary="List fixed assets")
async def list_assets(user: CurrentUser, db: DB, status_filter: str | None = None):
    stmt = select(FixedAsset).order_by(FixedAsset.acquired_on.desc())
    if status_filter:
        stmt = stmt.where(FixedAsset.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _hydrate(db, r) for r in rows]


@router.post("", response_model=FixedAssetResponse, status_code=status.HTTP_201_CREATED, summary="Register a new fixed asset")
async def create_asset(body: FixedAssetCreate, user: CurrentUser, db: DB):
    asset_account_id = body.asset_account_id or await _resolve_default_account(db, "1700")
    accum_id = body.accumulated_depreciation_account_id or await _resolve_default_account(db, "1750")
    expense_id = body.depreciation_expense_account_id or await _resolve_default_account(db, "6700")
    asset = FixedAsset(
        name=body.name,
        asset_tag=body.asset_tag,
        description=body.description,
        acquired_on=body.acquired_on,
        acquisition_cost=body.acquisition_cost,
        salvage_value=body.salvage_value,
        useful_life_months=body.useful_life_months,
        depreciation_method=body.depreciation_method,
        declining_balance_rate=body.declining_balance_rate,
        asset_account_id=asset_account_id,
        accumulated_depreciation_account_id=accum_id,
        depreciation_expense_account_id=expense_id,
        acquisition_bill_id=body.acquisition_bill_id,
        notes=body.notes,
    )
    db.add(asset)
    await db.flush()
    await db.commit()
    return await _hydrate(db, asset)


@router.get("/{asset_id}", response_model=FixedAssetDetail, summary="Fixed asset detail with schedule")
async def get_asset(asset_id: uuid.UUID, user: CurrentUser, db: DB):
    asset = (await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Fixed asset not found")
    base = await _hydrate(db, asset)
    schedule = [ScheduleRow(period_end=p, amount=a) for p, a in planned_schedule(asset)]
    posted = [
        e
        for e in (
            await db.execute(
                select(DepreciationEntry.period_end).where(
                    DepreciationEntry.fixed_asset_id == asset.id
                )
            )
        ).scalars().all()
    ]
    return FixedAssetDetail(**base.model_dump(), schedule=schedule, posted_periods=posted)


@router.patch("/{asset_id}", response_model=FixedAssetResponse, summary="Update a fixed asset")
async def update_asset(asset_id: uuid.UUID, body: FixedAssetUpdate, user: CurrentUser, db: DB):
    asset = (await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Fixed asset not found")
    if asset.status == "disposed":
        raise HTTPException(status_code=400, detail="Cannot edit a disposed asset")

    critical_locked = not await can_edit_critical_fields(db, asset.id)
    payload = body.model_dump(exclude_unset=True)
    if critical_locked:
        for k in ("acquisition_cost", "salvage_value", "useful_life_months", "depreciation_method", "declining_balance_rate"):
            if k in payload:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot edit '{k}' once depreciation has been posted; reverse those entries first.",
                )

    for k, v in payload.items():
        setattr(asset, k, v)
    await db.commit()
    return await _hydrate(db, asset)


@router.post("/post-depreciation", summary="Post depreciation through a period for selected (or all active) assets")
async def post_dep(body: DepreciationPostRequest, user: CurrentUser, db: DB):
    if body.asset_ids:
        assets = (
            await db.execute(
                select(FixedAsset).where(FixedAsset.id.in_(body.asset_ids))
            )
        ).scalars().all()
    else:
        assets = (
            await db.execute(
                select(FixedAsset).where(FixedAsset.status == "active")
            )
        ).scalars().all()

    posted_count = 0
    for a in assets:
        try:
            new_entries = await post_depreciation(db, asset_id=a.id, through=body.period_end)
            posted_count += len(new_entries)
        except FixedAssetError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {"posted_count": posted_count, "asset_count": len(assets)}


@router.post("/{asset_id}/dispose", response_model=FixedAssetResponse, summary="Dispose a fixed asset (sale or write-off)")
async def dispose(asset_id: uuid.UUID, body: DisposeRequest, user: CurrentUser, db: DB):
    gain_id = await _resolve_default_account(db, "4910")
    loss_id = await _resolve_default_account(db, "6710")
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
    except FixedAssetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return await _hydrate(db, asset)


@router.delete("/{asset_id}", status_code=204, summary="Delete a fixed asset (only if no entries and not disposed)")
async def delete_asset(asset_id: uuid.UUID, user: CurrentUser, db: DB):
    asset = (await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Fixed asset not found")
    if not await can_edit_critical_fields(db, asset.id):
        raise HTTPException(status_code=400, detail="Cannot delete an asset with depreciation entries")
    if asset.status == "disposed":
        raise HTTPException(status_code=400, detail="Cannot delete a disposed asset")
    await db.delete(asset)
    await db.commit()
