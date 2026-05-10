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
    total_rc_in = total_rc_out = Decimal("0")

    for profile in profiles:
        sale_stmt = select(Sale).where(Sale.tax_profile_id == profile.id, Sale.is_deleted == False)
        if date_from:
            sale_stmt = sale_stmt.where(Sale.date >= date_from)
        if date_to:
            sale_stmt = sale_stmt.where(Sale.date <= date_to)
        sales = (await db.execute(sale_stmt)).scalars().all()
        # #329 P2: reverse-charge sales are notional — the operator should
        # not actually collect tax. Bucket them separately so the books and
        # reporting stay reconcilable. Both sides should be equal in magnitude.
        if profile.is_reverse_charge:
            seller_collected = Decimal("0")
            marketplace_facilitated = Decimal("0")
            rc_in = sum((sale.tax_collected for sale in sales), Decimal("0"))
            rc_out = rc_in  # net-zero by definition
        else:
            seller_collected = sum((sale.tax_collected for sale in sales if sale.tax_treatment == "seller_collected"), Decimal("0"))
            marketplace_facilitated = sum((sale.tax_collected for sale in sales if sale.tax_treatment == "marketplace_facilitated"), Decimal("0"))
            rc_in = rc_out = Decimal("0")

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
            is_reverse_charge=profile.is_reverse_charge,
            reverse_charged_in=rc_in,
            reverse_charged_out=rc_out,
        ))
        total_seller += seller_collected
        total_marketplace += marketplace_facilitated
        total_remitted += remitted
        total_outstanding += outstanding
        total_rc_in += rc_in
        total_rc_out += rc_out

    return TaxLiabilitySummary(
        date_from=date_from,
        date_to=date_to,
        rows=rows,
        total_seller_collected=total_seller,
        total_marketplace_facilitated=total_marketplace,
        total_remitted=total_remitted,
        total_outstanding_liability=total_outstanding,
        total_reverse_charged_in=total_rc_in,
        total_reverse_charged_out=total_rc_out,
    )


@router.get(
    "/reports/component-breakdown",
    summary="Per-component tax breakdown for compound profiles (#329 P2)",
)
async def component_breakdown_report(
    admin: CurrentAdmin,
    db: DB,
    profile_id: uuid.UUID | None = Query(None, description="Filter to one profile; otherwise all active"),
    date_from: datetime.date | None = Query(None),
    date_to: datetime.date | None = Query(None),
):
    """For each tax profile, sum the period's sale subtotals (taxable base)
    and decompose across components. Useful for compound profiles like
    QC's GST+QST where remittance forms ask for each component separately.
    """
    from app.services.tax_service import compute_component_breakdown

    profile_stmt = select(TaxProfile).where(TaxProfile.is_active == True)  # noqa: E712
    if profile_id is not None:
        profile_stmt = profile_stmt.where(TaxProfile.id == profile_id)
    profiles = (await db.execute(profile_stmt)).scalars().all()

    out_rows: list[dict] = []
    grand_total = Decimal("0")
    for p in profiles:
        sale_stmt = select(Sale).where(Sale.tax_profile_id == p.id, Sale.is_deleted == False)  # noqa: E712
        if date_from:
            sale_stmt = sale_stmt.where(Sale.date >= date_from)
        if date_to:
            sale_stmt = sale_stmt.where(Sale.date <= date_to)
        sales = (await db.execute(sale_stmt)).scalars().all()
        # Sale.subtotal is the pre-tax base for this profile in the period.
        period_subtotal = sum((Decimal(s.subtotal) for s in sales), Decimal("0"))
        if period_subtotal == 0:
            continue
        breakdown = await compute_component_breakdown(
            db, profile_id=p.id, sales_subtotal=period_subtotal
        )
        for r in breakdown:
            out_rows.append(
                {
                    "profile_id": str(r.profile_id),
                    "profile_name": r.profile_name,
                    "component_name": r.component_name,
                    "rate": str(r.rate),
                    "sales_subtotal": str(r.sales_subtotal),
                    "estimated_tax": str(r.estimated_tax),
                }
            )
            grand_total += r.estimated_tax

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "rows": out_rows,
        "total_estimated_tax": str(grand_total),
    }


@router.post("/compute", summary="Compute tax breakdown for a subtotal against a profile (#258 Phase 2)")
async def compute_tax(
    db: DB,
    profile_id: uuid.UUID,
    subtotal: Decimal,
):
    """Returns one row per layer for compound profiles, one for single-rate.
    Each row carries `component_name`, `base`, `rate`, `amount`,
    `account_id`, and `is_reverse_charge`. Operators (and future invoice
    creation flows) can use this to preview compound + reverse-charge
    treatment before posting.
    """
    from app.services.tax_service import compute_for_line

    rows = await compute_for_line(db, profile_id=profile_id, subtotal=subtotal)
    if not rows:
        raise HTTPException(status_code=404, detail="Tax profile not found")
    total = sum((r.amount for r in rows), Decimal("0"))
    return {
        "profile_id": str(profile_id),
        "subtotal": str(subtotal),
        "total_tax": str(total),
        "is_reverse_charge": rows[0].is_reverse_charge,
        "components": [
            {
                "component_name": r.component_name,
                "base": str(r.base),
                "rate": str(r.rate),
                "amount": str(r.amount),
                "account_id": str(r.account_id) if r.account_id else None,
            }
            for r in rows
        ],
    }
