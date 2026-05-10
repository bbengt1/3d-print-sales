from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.withholding_profile import WithholdingProfile
from app.services.withholding_service import (
    WithholdingError,
    apply_payment_with_withholding,
)


router = APIRouter(prefix="/withholding", tags=["Withholding"])


class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    rate_pct: Decimal = Field(..., gt=0)
    liability_account_id: uuid.UUID
    is_active: bool = True


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    rate_pct: Decimal | None = Field(None, gt=0)
    liability_account_id: uuid.UUID | None = None
    is_active: bool | None = None


class ProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    rate_pct: Decimal
    liability_account_id: uuid.UUID
    is_active: bool


def _to_resp(p: WithholdingProfile) -> ProfileResponse:
    return ProfileResponse(
        id=p.id, name=p.name, rate_pct=Decimal(p.rate_pct),
        liability_account_id=p.liability_account_id, is_active=p.is_active,
    )


@router.get("/profiles", response_model=list[ProfileResponse], summary="List withholding profiles")
async def list_profiles(user: CurrentUser, db: DB):
    rows = (await db.execute(select(WithholdingProfile))).scalars().all()
    return [_to_resp(p) for p in rows]


@router.post("/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED, summary="Create withholding profile")
async def create_profile(body: ProfileCreate, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    p = WithholdingProfile(**body.model_dump())
    db.add(p)
    await db.commit()
    return _to_resp(p)


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse, summary="Update withholding profile")
async def update_profile(profile_id: uuid.UUID, body: ProfileUpdate, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    p = (await db.execute(select(WithholdingProfile).where(WithholdingProfile.id == profile_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    return _to_resp(p)


class ApplyWithholdingRequest(BaseModel):
    gross_amount: Decimal = Field(..., gt=0)
    cash_account_id: uuid.UUID
    paid_on: datetime.date | None = None


@router.post(
    "/invoices/{invoice_id}/apply-payment-with-withholding",
    summary="#263 P2: Apply customer payment with withholding split",
)
async def apply_payment_with_withholding_ep(
    invoice_id: uuid.UUID, body: ApplyWithholdingRequest, user: CurrentUser, db: DB
):
    try:
        result = await apply_payment_with_withholding(
            db,
            invoice_id=invoice_id,
            gross_amount=body.gross_amount,
            cash_account_id=body.cash_account_id,
            paid_on=body.paid_on,
        )
    except WithholdingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result
