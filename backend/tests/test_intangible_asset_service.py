from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.intangible_asset import IntangibleAsset
from app.services.intangible_asset_service import (
    IntangibleAssetError,
    can_edit_critical_fields,
    compute_book_value,
    dispose_asset,
    planned_schedule,
    post_amortization,
)


async def _accounts(db_session):
    return {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}


async def _make_asset(
    db_session,
    *,
    cost="1200",
    salvage="0",
    life_months=12,
    method="straight_line",
    rate=None,
    acquired_on=None,
):
    accts = await _accounts(db_session)
    asset = IntangibleAsset(
        name="CAD subscription",
        acquired_on=acquired_on or datetime.date(2026, 1, 15),
        acquisition_cost=Decimal(cost),
        salvage_value=Decimal(salvage),
        useful_life_months=life_months,
        amortization_method=method,
        declining_balance_rate=Decimal(rate) if rate is not None else None,
        asset_account_id=accts["1800"].id,
        accumulated_amortization_account_id=accts["1850"].id,
        amortization_expense_account_id=accts["6750"].id,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


@pytest.mark.asyncio
async def test_sl_schedule_sums_to_cost(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    sched = planned_schedule(a)
    assert len(sched) == 12
    total = sum((amt for _, amt in sched), Decimal("0"))
    assert total == Decimal("1200.00")


@pytest.mark.asyncio
async def test_db_schedule_front_loaded(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=24, method="declining_balance")
    sched = planned_schedule(a)
    assert sched[0][1] > sched[-1][1]
    total = sum((amt for _, amt in sched), Decimal("0"))
    assert total == Decimal("1200.00")


@pytest.mark.asyncio
async def test_post_then_book_value(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    new_entries = await post_amortization(db_session, asset_id=a.id, through=datetime.date(2026, 4, 30))
    assert len(new_entries) == 4
    book = await compute_book_value(db_session, a.id)
    assert book == Decimal("800.00")


@pytest.mark.asyncio
async def test_idempotent_reposting(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    await post_amortization(db_session, asset_id=a.id, through=datetime.date(2026, 4, 30))
    new = await post_amortization(db_session, asset_id=a.id, through=datetime.date(2026, 4, 30))
    assert new == []


@pytest.mark.asyncio
async def test_full_life_reaches_salvage(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="200", life_months=12)
    await post_amortization(db_session, asset_id=a.id, through=datetime.date(2027, 12, 31))
    assert (await compute_book_value(db_session, a.id)) == Decimal("200.00")
    refreshed = (await db_session.execute(select(IntangibleAsset).where(IntangibleAsset.id == a.id))).scalar_one()
    assert refreshed.status == "fully_amortized"


@pytest.mark.asyncio
async def test_critical_fields_locked_after_first_post(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    assert await can_edit_critical_fields(db_session, a.id) is True
    await post_amortization(db_session, asset_id=a.id, through=datetime.date(2026, 1, 31))
    assert await can_edit_critical_fields(db_session, a.id) is False


@pytest.mark.asyncio
async def test_dispose_with_gain(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    await post_amortization(db_session, asset_id=a.id, through=datetime.date(2026, 3, 31))
    asset = await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 3, 31),
        proceeds=Decimal("1000"),
        proceeds_account_id=accts["1000"].id,
        gain_account_id=accts["4920"].id,
        loss_account_id=accts["6760"].id,
    )
    assert asset.status == "disposed"


@pytest.mark.asyncio
async def test_dispose_with_no_proceeds_loss(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    asset = await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 6, 30),
        proceeds=None,
        proceeds_account_id=None,
        gain_account_id=accts["4920"].id,
        loss_account_id=accts["6760"].id,
    )
    assert asset.status == "disposed"


@pytest.mark.asyncio
async def test_cannot_dispose_already_disposed(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 3, 31),
        proceeds=None,
        proceeds_account_id=None,
        gain_account_id=accts["4920"].id,
        loss_account_id=accts["6760"].id,
    )
    with pytest.raises(IntangibleAssetError):
        await dispose_asset(
            db_session,
            asset_id=a.id,
            disposed_on=datetime.date(2026, 4, 30),
            proceeds=None,
            proceeds_account_id=None,
            gain_account_id=accts["4920"].id,
            loss_account_id=accts["6760"].id,
        )
