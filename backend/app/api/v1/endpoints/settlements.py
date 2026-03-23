from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentAdmin
from app.models.marketplace_settlement import MarketplaceSettlement
from app.models.sale import Sale
from app.models.sales_channel import SalesChannel
from app.models.settlement_line import SettlementLine
from app.schemas.settlement import (
    MarketplaceSettlementCreate,
    MarketplaceSettlementResponse,
    SettlementReconciliationRow,
    SettlementReconciliationSummary,
)

router = APIRouter(prefix="/settlements", tags=["Settlements"])


async def _calculate_expected_net(db: DB, channel_id, period_start, period_end, adjustments: Decimal, reserves_held: Decimal, lines=None):
    if lines:
        gross_sales = sum((line.amount for line in lines if line.line_type == "sale"), Decimal("0"))
        marketplace_fees = sum((abs(line.amount) for line in lines if line.line_type == "fee"), Decimal("0"))
        expected_net = gross_sales - marketplace_fees + adjustments - reserves_held
        return gross_sales, marketplace_fees, expected_net

    sales = (
        await db.execute(
            select(Sale).where(
                Sale.channel_id == channel_id,
                Sale.is_deleted == False,
                Sale.date >= period_start,
                Sale.date <= period_end,
                Sale.status != "cancelled",
            )
        )
    ).scalars().all()
    gross_sales = sum((sale.total for sale in sales), Decimal("0"))
    marketplace_fees = sum((sale.platform_fees for sale in sales), Decimal("0"))
    expected_net = gross_sales - marketplace_fees + adjustments - reserves_held
    return gross_sales, marketplace_fees, expected_net


@router.post("", response_model=MarketplaceSettlementResponse, status_code=status.HTTP_201_CREATED, summary="Create marketplace settlement (admin only)")
async def create_settlement(body: MarketplaceSettlementCreate, admin: CurrentAdmin, db: DB):
    existing = (await db.execute(select(MarketplaceSettlement).where(MarketplaceSettlement.settlement_number == body.settlement_number))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Settlement '{body.settlement_number}' already exists")

    channel = (await db.execute(select(SalesChannel).where(SalesChannel.id == body.channel_id))).scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Sales channel not found")

    calc_gross, calc_fees, expected_net = await _calculate_expected_net(db, body.channel_id, body.period_start, body.period_end, body.adjustments, body.reserves_held, body.lines)
    gross_sales = body.gross_sales if body.gross_sales != 0 else calc_gross
    marketplace_fees = body.marketplace_fees if body.marketplace_fees != 0 else calc_fees
    discrepancy = body.net_deposit - expected_net

    settlement = MarketplaceSettlement(
        settlement_number=body.settlement_number,
        channel_id=body.channel_id,
        period_start=body.period_start,
        period_end=body.period_end,
        payout_date=body.payout_date,
        gross_sales=gross_sales,
        marketplace_fees=marketplace_fees,
        adjustments=body.adjustments,
        reserves_held=body.reserves_held,
        net_deposit=body.net_deposit,
        expected_net=expected_net,
        discrepancy_amount=discrepancy,
        notes=body.notes,
    )
    db.add(settlement)
    await db.flush()

    for line in body.lines:
        db.add(SettlementLine(settlement_id=settlement.id, **line.model_dump()))

    await db.commit()
    result = await db.execute(select(MarketplaceSettlement).options(selectinload(MarketplaceSettlement.lines)).where(MarketplaceSettlement.id == settlement.id))
    return result.scalar_one()


@router.get("", response_model=list[MarketplaceSettlementResponse], summary="List marketplace settlements")
async def list_settlements(admin: CurrentAdmin, db: DB, channel_id: uuid.UUID | None = Query(None)):
    stmt = select(MarketplaceSettlement).options(selectinload(MarketplaceSettlement.lines)).order_by(MarketplaceSettlement.payout_date.desc(), MarketplaceSettlement.created_at.desc())
    if channel_id:
        stmt = stmt.where(MarketplaceSettlement.channel_id == channel_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/reports/reconciliation", response_model=SettlementReconciliationSummary, summary="Settlement reconciliation report (admin only)")
async def settlement_reconciliation_report(admin: CurrentAdmin, db: DB, channel_id: uuid.UUID | None = Query(None)):
    stmt = select(MarketplaceSettlement).order_by(MarketplaceSettlement.payout_date.desc())
    if channel_id:
        stmt = stmt.where(MarketplaceSettlement.channel_id == channel_id)
    settlements = (await db.execute(stmt)).scalars().all()

    rows = [
        SettlementReconciliationRow(
            settlement_id=s.id,
            settlement_number=s.settlement_number,
            channel_id=s.channel_id,
            period_start=s.period_start,
            period_end=s.period_end,
            payout_date=s.payout_date,
            gross_sales=s.gross_sales,
            marketplace_fees=s.marketplace_fees,
            adjustments=s.adjustments,
            reserves_held=s.reserves_held,
            net_deposit=s.net_deposit,
            expected_net=s.expected_net,
            discrepancy_amount=s.discrepancy_amount,
        )
        for s in settlements
    ]

    total_gross = sum((s.gross_sales for s in settlements), Decimal("0"))
    total_fees = sum((s.marketplace_fees for s in settlements), Decimal("0"))
    total_adjustments = sum((s.adjustments for s in settlements), Decimal("0"))
    total_reserves = sum((s.reserves_held for s in settlements), Decimal("0"))
    total_net = sum((s.net_deposit for s in settlements), Decimal("0"))
    total_expected = sum((s.expected_net for s in settlements), Decimal("0"))
    total_discrepancy = sum((s.discrepancy_amount for s in settlements), Decimal("0"))

    return SettlementReconciliationSummary(
        rows=rows,
        total_gross_sales=total_gross,
        total_marketplace_fees=total_fees,
        total_adjustments=total_adjustments,
        total_reserves_held=total_reserves,
        total_net_deposit=total_net,
        total_expected_net=total_expected,
        total_discrepancy=total_discrepancy,
    )
