from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DB, CurrentAdmin
from app.models.sale import Sale
from app.models.tax_profile import TaxProfile
from app.models.tax_remittance import TaxRemittance
from app.schemas.tax import (
    TaxLiabilityRow,
    TaxLiabilitySummary,
    TaxProfileCreate,
    TaxProfileResponse,
    TaxProfileUpdate,
    TaxRemittanceCreate,
    TaxRemittanceResponse,
)

router = APIRouter(prefix="/tax", tags=["Tax"])


@router.post("/profiles", response_model=TaxProfileResponse, status_code=status.HTTP_201_CREATED, summary="Create tax profile (admin only)")
async def create_tax_profile(body: TaxProfileCreate, admin: CurrentAdmin, db: DB):
    existing = (await db.execute(select(TaxProfile).where(TaxProfile.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Tax profile '{body.name}' already exists")
    profile = TaxProfile(**body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/profiles", response_model=list[TaxProfileResponse], summary="List tax profiles")
async def list_tax_profiles(admin: CurrentAdmin, db: DB, is_active: bool | None = Query(None)):
    stmt = select(TaxProfile).order_by(TaxProfile.name.asc())
    if is_active is not None:
        stmt = stmt.where(TaxProfile.is_active == is_active)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/profiles/{profile_id}", response_model=TaxProfileResponse, summary="Update tax profile (admin only)")
async def update_tax_profile(profile_id: uuid.UUID, body: TaxProfileUpdate, admin: CurrentAdmin, db: DB):
    profile = (await db.execute(select(TaxProfile).where(TaxProfile.id == profile_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tax profile not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/remittances", response_model=TaxRemittanceResponse, status_code=status.HTTP_201_CREATED, summary="Record tax remittance (admin only)")
async def record_tax_remittance(body: TaxRemittanceCreate, admin: CurrentAdmin, db: DB):
    profile = (await db.execute(select(TaxProfile).where(TaxProfile.id == body.tax_profile_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tax profile not found")
    remittance = TaxRemittance(**body.model_dump())
    db.add(remittance)
    await db.commit()
    await db.refresh(remittance)
    return remittance


@router.get("/remittances", response_model=list[TaxRemittanceResponse], summary="List tax remittances")
async def list_tax_remittances(admin: CurrentAdmin, db: DB, tax_profile_id: uuid.UUID | None = Query(None)):
    stmt = select(TaxRemittance).order_by(TaxRemittance.remittance_date.desc(), TaxRemittance.created_at.desc())
    if tax_profile_id:
        stmt = stmt.where(TaxRemittance.tax_profile_id == tax_profile_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/reports/liability", response_model=TaxLiabilitySummary, summary="Tax liability report (admin only)")
async def tax_liability_report(admin: CurrentAdmin, db: DB, date_from: datetime.date | None = Query(None), date_to: datetime.date | None = Query(None)):
    profiles = (await db.execute(select(TaxProfile).where(TaxProfile.is_active == True))).scalars().all()
    rows: list[TaxLiabilityRow] = []
    total_seller = total_marketplace = total_remitted = total_outstanding = Decimal("0")

    for profile in profiles:
        sale_stmt = select(Sale).where(Sale.tax_profile_id == profile.id, Sale.is_deleted == False)
        if date_from:
            sale_stmt = sale_stmt.where(Sale.date >= date_from)
        if date_to:
            sale_stmt = sale_stmt.where(Sale.date <= date_to)
        sales = (await db.execute(sale_stmt)).scalars().all()
        seller_collected = sum((sale.tax_collected for sale in sales if sale.tax_treatment == "seller_collected"), Decimal("0"))
        marketplace_facilitated = sum((sale.tax_collected for sale in sales if sale.tax_treatment == "marketplace_facilitated"), Decimal("0"))

        remit_stmt = select(TaxRemittance).where(TaxRemittance.tax_profile_id == profile.id)
        if date_from:
            remit_stmt = remit_stmt.where(TaxRemittance.period_end >= date_from)
        if date_to:
            remit_stmt = remit_stmt.where(TaxRemittance.period_start <= date_to)
        remittances = (await db.execute(remit_stmt)).scalars().all()
        remitted = sum((row.amount for row in remittances), Decimal("0"))
        outstanding = seller_collected - remitted

        rows.append(TaxLiabilityRow(
            tax_profile_id=profile.id,
            tax_profile_name=profile.name,
            jurisdiction=profile.jurisdiction,
            seller_collected=seller_collected,
            marketplace_facilitated=marketplace_facilitated,
            remitted=remitted,
            outstanding_liability=outstanding,
        ))
        total_seller += seller_collected
        total_marketplace += marketplace_facilitated
        total_remitted += remitted
        total_outstanding += outstanding

    return TaxLiabilitySummary(
        date_from=date_from,
        date_to=date_to,
        rows=rows,
        total_seller_collected=total_seller,
        total_marketplace_facilitated=total_marketplace,
        total_remitted=total_remitted,
        total_outstanding_liability=total_outstanding,
    )
