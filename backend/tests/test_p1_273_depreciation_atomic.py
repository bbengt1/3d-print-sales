"""Regression for Codex P1 on PR #273.

`post_depreciation` posts one journal entry per month inside a loop. Each
call to `create_journal_entry` commits immediately, so if a later month
fails the closed-period guard (or any accounting validation), earlier
months were already persisted, leaving the asset partially depreciated and
breaking all-or-nothing semantics.

The fix pre-validates the closed-period guard for every month up front
before writing anything. This test exercises that exact failure mode: the
first N-1 months are open, the Nth is in a closed period. The call must
raise and leave NO depreciation rows (and no depreciation journal entries)
persisted for the asset.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.fixed_asset import DepreciationEntry, FixedAsset
from app.models.journal_entry import JournalEntry
from app.services.fixed_asset_service import FixedAssetError, post_depreciation


async def _accounts(db_session):
    by_code = {}
    for a in (await db_session.execute(select(Account))).scalars().all():
        by_code[a.code] = a
    return by_code


async def _make_asset(db_session, *, acquired_on, life_months=12, cost="1200"):
    accts = await _accounts(db_session)
    asset = FixedAsset(
        name="Atomic posting printer",
        acquired_on=acquired_on,
        acquisition_cost=Decimal(cost),
        salvage_value=Decimal("0"),
        useful_life_months=life_months,
        depreciation_method="straight_line",
        asset_account_id=accts["1700"].id,
        accumulated_depreciation_account_id=accts["1750"].id,
        depreciation_expense_account_id=accts["6700"].id,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


@pytest.mark.asyncio
async def test_post_depreciation_atomic_when_later_period_closed(db_session):
    """First three months open, fourth month is in a closed period.

    The call must raise and persist nothing — no DepreciationEntry rows for
    the asset and no `source_type='depreciation'` JournalEntry rows tied to
    it.
    """
    asset = await _make_asset(
        db_session, acquired_on=datetime.date(2026, 1, 15), life_months=12
    )

    # Open periods for Jan/Feb/Mar 2026.
    for month, key in [(1, "2026-01"), (2, "2026-02"), (3, "2026-03")]:
        last = 31 if month in (1, 3) else 28
        db_session.add(
            AccountingPeriod(
                period_key=key,
                name=f"2026-{month:02d}",
                start_date=datetime.date(2026, month, 1),
                end_date=datetime.date(2026, month, last),
                status="open",
            )
        )
    # Closed period for April 2026 — this is the one that should trip.
    db_session.add(
        AccountingPeriod(
            period_key="2026-04",
            name="2026-04",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2026, 4, 30),
            status="closed",
        )
    )
    await db_session.commit()

    with pytest.raises(FixedAssetError, match="closed"):
        await post_depreciation(
            db_session, asset_id=asset.id, through=datetime.date(2026, 4, 30)
        )

    # All-or-nothing: no DepreciationEntry rows should exist for this asset.
    de_rows = (
        await db_session.execute(
            select(DepreciationEntry).where(
                DepreciationEntry.fixed_asset_id == asset.id
            )
        )
    ).scalars().all()
    assert de_rows == [], f"expected no depreciation entries, got {len(de_rows)}"

    # And no depreciation JournalEntry rows for this asset either — the
    # earlier months must not have been persisted by an autocommitting
    # `create_journal_entry`.
    je_rows = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.source_type == "depreciation",
                JournalEntry.source_id == str(asset.id),
            )
        )
    ).scalars().all()
    assert je_rows == [], (
        f"expected no depreciation journal entries, got {len(je_rows)} "
        f"(partial commits leaked across the loop)"
    )


@pytest.mark.asyncio
async def test_post_depreciation_succeeds_when_all_periods_open(db_session):
    """Sanity: when every month's period is open, posting works as before."""
    asset = await _make_asset(
        db_session, acquired_on=datetime.date(2026, 1, 15), life_months=12
    )

    for month, key, last in [
        (1, "2026-01", 31),
        (2, "2026-02", 28),
        (3, "2026-03", 31),
        (4, "2026-04", 30),
    ]:
        db_session.add(
            AccountingPeriod(
                period_key=key,
                name=f"2026-{month:02d}",
                start_date=datetime.date(2026, month, 1),
                end_date=datetime.date(2026, month, last),
                status="open",
            )
        )
    await db_session.commit()

    new_entries = await post_depreciation(
        db_session, asset_id=asset.id, through=datetime.date(2026, 4, 30)
    )
    assert len(new_entries) == 4
