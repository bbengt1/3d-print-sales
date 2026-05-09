from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

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


# ---------- helpers ----------


async def _accounts(db_session):
    by_code = {}
    for a in (await db_session.execute(select(Account))).scalars().all():
        by_code[a.code] = a
    return by_code


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
    asset = FixedAsset(
        name="Test printer",
        acquired_on=acquired_on or datetime.date(2026, 1, 15),
        acquisition_cost=Decimal(cost),
        salvage_value=Decimal(salvage),
        useful_life_months=life_months,
        depreciation_method=method,
        declining_balance_rate=Decimal(rate) if rate is not None else None,
        asset_account_id=accts["1700"].id,
        accumulated_depreciation_account_id=accts["1750"].id,
        depreciation_expense_account_id=accts["6700"].id,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


# ---------- straight-line ----------


@pytest.mark.asyncio
async def test_sl_schedule_sums_to_cost_minus_salvage(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    sched = planned_schedule(a)
    assert len(sched) == 12
    total = sum((amt for _, amt in sched), Decimal("0"))
    assert total == Decimal("1200.00")
    # Each month roughly equal
    assert all(amt == Decimal("100.00") for _, amt in sched[:-1])


@pytest.mark.asyncio
async def test_sl_with_salvage(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="200", life_months=10)
    sched = planned_schedule(a)
    total = sum((amt for _, amt in sched), Decimal("0"))
    assert total == Decimal("1000.00")


@pytest.mark.asyncio
async def test_post_depreciation_through_3_months_idempotent(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    # Post through Apr 30 (Jan/Feb/Mar/Apr = 4 month-ends after Jan 15 acquisition)
    # First period_end is Jan 31 (acquisition month).
    new_entries = await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2026, 4, 30))
    assert len(new_entries) == 4
    # Re-running through the same date is a no-op
    new_entries2 = await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2026, 4, 30))
    assert new_entries2 == []
    book = await compute_book_value(db_session, a.id)
    assert book == Decimal("800.00")


@pytest.mark.asyncio
async def test_post_depreciation_full_life_brings_book_value_to_salvage(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="200", life_months=12)
    await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2027, 12, 31))
    book = await compute_book_value(db_session, a.id)
    assert book == Decimal("200.00")
    # Status auto-flipped
    refreshed = (await db_session.execute(select(FixedAsset).where(FixedAsset.id == a.id))).scalar_one()
    assert refreshed.status == "fully_depreciated"


# ---------- declining-balance ----------


@pytest.mark.asyncio
async def test_db_schedule_front_loaded_and_reaches_salvage(db_session):
    a = await _make_asset(
        db_session,
        cost="1200",
        salvage="0",
        life_months=24,
        method="declining_balance",
    )
    sched = planned_schedule(a)
    total = sum((amt for _, amt in sched), Decimal("0"))
    assert total == Decimal("1200.00")
    # Front-loaded — first month exceeds last month
    assert sched[0][1] > sched[-1][1]


@pytest.mark.asyncio
async def test_db_explicit_rate(db_session):
    a = await _make_asset(
        db_session,
        cost="1000",
        salvage="100",
        life_months=12,
        method="declining_balance",
        rate="0.40",
    )
    sched = planned_schedule(a)
    total = sum((amt for _, amt in sched), Decimal("0"))
    assert total == Decimal("900.00")


# ---------- edits ----------


@pytest.mark.asyncio
async def test_critical_fields_locked_after_first_post(db_session):
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    assert await can_edit_critical_fields(db_session, a.id) is True
    await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2026, 1, 31))
    assert await can_edit_critical_fields(db_session, a.id) is False


# ---------- disposal ----------


@pytest.mark.asyncio
async def test_dispose_with_proceeds_above_book_posts_gain(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    # Post 3 months → book value = 900
    await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2026, 3, 31))
    pre_book = await compute_book_value(db_session, a.id)
    assert pre_book == Decimal("900.00")

    asset = await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 3, 31),
        proceeds=Decimal("1000"),
        proceeds_account_id=accts["1000"].id,
        gain_account_id=accts["4910"].id,
        loss_account_id=accts["6710"].id,
    )
    assert asset.status == "disposed"
    assert asset.disposal_journal_entry_id is not None


@pytest.mark.asyncio
async def test_dispose_with_proceeds_below_book_posts_loss(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2026, 3, 31))
    asset = await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 3, 31),
        proceeds=Decimal("500"),
        proceeds_account_id=accts["1000"].id,
        gain_account_id=accts["4910"].id,
        loss_account_id=accts["6710"].id,
    )
    assert asset.status == "disposed"


@pytest.mark.asyncio
async def test_dispose_with_no_proceeds_writes_off(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    asset = await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 6, 30),
        proceeds=None,
        proceeds_account_id=None,
        gain_account_id=accts["4910"].id,
        loss_account_id=accts["6710"].id,
    )
    assert asset.status == "disposed"
    assert asset.disposal_proceeds is None


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
        gain_account_id=accts["4910"].id,
        loss_account_id=accts["6710"].id,
    )
    with pytest.raises(FixedAssetError):
        await dispose_asset(
            db_session,
            asset_id=a.id,
            disposed_on=datetime.date(2026, 4, 30),
            proceeds=None,
            proceeds_account_id=None,
            gain_account_id=accts["4910"].id,
            loss_account_id=accts["6710"].id,
        )


@pytest.mark.asyncio
async def test_post_depreciation_refused_on_disposed_asset(db_session):
    accts = await _accounts(db_session)
    a = await _make_asset(db_session, cost="1200", salvage="0", life_months=12)
    await dispose_asset(
        db_session,
        asset_id=a.id,
        disposed_on=datetime.date(2026, 3, 31),
        proceeds=None,
        proceeds_account_id=None,
        gain_account_id=accts["4910"].id,
        loss_account_id=accts["6710"].id,
    )
    with pytest.raises(FixedAssetError):
        await post_depreciation(db_session, asset_id=a.id, through=datetime.date(2026, 4, 30))
