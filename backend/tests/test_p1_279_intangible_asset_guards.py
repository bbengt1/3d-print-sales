"""Regression for Codex P1 review on PR #279.

Two related defects in the intangible-asset register:

(1) `dispose_asset` did not validate `disposed_on >= acquired_on`. A
    request could create a disposal journal entry that predated the
    asset's acquisition — an impossible lifecycle.

(2) The `/post-amortization` bulk endpoint looped over assets and called
    `post_amortization` for each. `post_amortization` writes JEs through
    `create_journal_entry`, which commits internally. If the second
    asset raised after the first had already committed entries, the API
    returned 400 with partial state already persisted — unsafe for
    retries and reconciliation.

The fix pre-validates closed-period and disposal guards for every asset
before any writes, mirroring the PR #273 atomicity fix in
`fixed_asset_service`. A failure in any asset must leave zero
amortization rows / amortization JEs from the request.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.intangible_asset import AmortizationEntry, IntangibleAsset
from app.models.journal_entry import JournalEntry
from app.services.intangible_asset_service import (
    IntangibleAssetError,
    dispose_asset,
)


async def _accounts(db_session):
    return {
        a.code: a
        for a in (await db_session.execute(select(Account))).scalars().all()
    }


async def _make_asset(
    db_session,
    *,
    name="CAD subscription",
    cost="1200",
    salvage="0",
    life_months=12,
    acquired_on=None,
):
    accts = await _accounts(db_session)
    asset = IntangibleAsset(
        name=name,
        acquired_on=acquired_on or datetime.date(2026, 1, 15),
        acquisition_cost=Decimal(cost),
        salvage_value=Decimal(salvage),
        useful_life_months=life_months,
        amortization_method="straight_line",
        asset_account_id=accts["1800"].id,
        accumulated_amortization_account_id=accts["1850"].id,
        amortization_expense_account_id=accts["6750"].id,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


@pytest.mark.asyncio
async def test_dispose_before_acquired_on_rejected(db_session):
    """`dispose_asset` must reject a disposal date earlier than acquisition.

    No amortization entry, no disposal JE, and no status mutation should
    occur — the request is rejected before any side effects.
    """
    accts = await _accounts(db_session)
    asset = await _make_asset(
        db_session, acquired_on=datetime.date(2026, 6, 15)
    )
    await db_session.commit()

    bad_disposal = datetime.date(2026, 1, 10)  # before 2026-06-15

    with pytest.raises(IntangibleAssetError, match="before"):
        await dispose_asset(
            db_session,
            asset_id=asset.id,
            disposed_on=bad_disposal,
            proceeds=Decimal("100"),
            proceeds_account_id=accts["1000"].id,
            gain_account_id=accts["4920"].id,
            loss_account_id=accts["6760"].id,
        )

    # No amortization entries should exist.
    ae_rows = (
        await db_session.execute(
            select(AmortizationEntry).where(
                AmortizationEntry.intangible_asset_id == asset.id
            )
        )
    ).scalars().all()
    assert ae_rows == [], "no amortization should be posted on rejected disposal"

    # No disposal JE for this asset.
    je_rows = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.source_type == "intangible_asset_disposal",
                JournalEntry.source_id == str(asset.id),
            )
        )
    ).scalars().all()
    assert je_rows == [], "no disposal JE should be created"

    # And the asset must remain active (status not flipped to disposed).
    refreshed = (
        await db_session.execute(
            select(IntangibleAsset).where(IntangibleAsset.id == asset.id)
        )
    ).scalar_one()
    assert refreshed.status != "disposed"
    assert refreshed.disposed_on is None


@pytest.mark.asyncio
async def test_dispose_on_acquisition_date_allowed(db_session):
    """Boundary: `disposed_on == acquired_on` is permitted (zero-life)."""
    accts = await _accounts(db_session)
    acq = datetime.date(2026, 6, 15)
    asset = await _make_asset(db_session, acquired_on=acq)
    await db_session.commit()

    result = await dispose_asset(
        db_session,
        asset_id=asset.id,
        disposed_on=acq,
        proceeds=Decimal("0"),
        proceeds_account_id=None,
        gain_account_id=accts["4920"].id,
        loss_account_id=accts["6760"].id,
    )
    assert result.status == "disposed"


@pytest.mark.asyncio
async def test_bulk_amortization_atomic_when_one_asset_invalid(client, auth_headers, db_session):
    """Two assets in one bulk request, second hits a closed period.

    Asset A has all open periods. Asset B's target month falls in a
    closed accounting period. The bulk endpoint must reject the request
    AND leave zero `AmortizationEntry` rows and zero amortization JEs
    from this call. (Without the fix, asset A would have been committed
    by `create_journal_entry` before asset B raised.)
    """
    a1 = await _make_asset(
        db_session,
        name="Asset A",
        acquired_on=datetime.date(2026, 1, 15),
    )
    a2 = await _make_asset(
        db_session,
        name="Asset B",
        acquired_on=datetime.date(2026, 1, 15),
    )
    # Open periods for Jan/Feb 2026; closed period for March 2026 (this
    # is what trips asset B's plan but not the assets' shared earlier
    # months — every "through 2026-03-31" call needs the March row open).
    db_session.add_all(
        [
            AccountingPeriod(
                period_key="2026-01",
                name="2026-01",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 31),
                status="open",
            ),
            AccountingPeriod(
                period_key="2026-02",
                name="2026-02",
                start_date=datetime.date(2026, 2, 1),
                end_date=datetime.date(2026, 2, 28),
                status="open",
            ),
            AccountingPeriod(
                period_key="2026-03",
                name="2026-03",
                start_date=datetime.date(2026, 3, 1),
                end_date=datetime.date(2026, 3, 31),
                status="closed",
            ),
        ]
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/intangible-assets/post-amortization",
        json={
            "period_end": "2026-03-31",
            "asset_ids": [str(a1.id), str(a2.id)],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "closed" in resp.json()["detail"].lower()

    # Cross-asset atomicity: NEITHER asset's amortization should have been
    # committed — including asset A's earlier months that would otherwise
    # have leaked through `create_journal_entry`'s internal commit.
    ae_rows = (
        await db_session.execute(
            select(AmortizationEntry).where(
                AmortizationEntry.intangible_asset_id.in_([a1.id, a2.id])
            )
        )
    ).scalars().all()
    assert ae_rows == [], (
        f"expected zero amortization entries after atomic failure, "
        f"got {len(ae_rows)} (partial bulk commit leaked)"
    )

    je_rows = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.source_type == "amortization",
                JournalEntry.source_id.in_([str(a1.id), str(a2.id)]),
            )
        )
    ).scalars().all()
    assert je_rows == [], (
        f"expected zero amortization JEs after atomic failure, got "
        f"{len(je_rows)} (partial bulk commit leaked)"
    )
