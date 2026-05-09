from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.tax_profile import TaxProfile, TaxProfileComponent
from app.services.tax_service import compute_for_line


async def _accounts(db_session):
    return {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}


@pytest.mark.asyncio
async def test_single_rate_profile(db_session):
    p = TaxProfile(name="Sales tax 7%", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add(p)
    await db_session.flush()
    out = await compute_for_line(db_session, profile_id=p.id, subtotal=Decimal("100"))
    assert len(out) == 1
    assert out[0].amount == Decimal("7.00")
    assert out[0].rate == Decimal("7.000")


@pytest.mark.asyncio
async def test_compound_profile_two_layers(db_session):
    """Quebec-style: 5% federal then 9.975% provincial on (base + federal)."""
    p = TaxProfile(name="QC compound", jurisdiction="QC", tax_rate=Decimal("0"), is_compound=True)
    db_session.add(p)
    await db_session.flush()
    db_session.add(TaxProfileComponent(profile_id=p.id, name="GST", rate=Decimal("5.000"), apply_order=0))
    db_session.add(TaxProfileComponent(profile_id=p.id, name="QST", rate=Decimal("9.975"), apply_order=1))
    await db_session.flush()

    out = await compute_for_line(db_session, profile_id=p.id, subtotal=Decimal("100"))
    assert len(out) == 2
    assert out[0].amount == Decimal("5.00")  # 100 * 5%
    # QST: 105 * 9.975% = 10.47375 → 10.47
    assert out[1].amount == Decimal("10.47")


@pytest.mark.asyncio
async def test_reverse_charge_flag_propagates(db_session):
    p = TaxProfile(
        name="EU reverse charge", jurisdiction="EU", tax_rate=Decimal("20.000"),
        is_reverse_charge=True,
    )
    db_session.add(p)
    await db_session.flush()
    out = await compute_for_line(db_session, profile_id=p.id, subtotal=Decimal("100"))
    assert out[0].is_reverse_charge is True
    assert out[0].amount == Decimal("20.00")


@pytest.mark.asyncio
async def test_zero_rate_returns_zero_amount(db_session):
    p = TaxProfile(name="Zero", jurisdiction="X", tax_rate=Decimal("0"))
    db_session.add(p)
    await db_session.flush()
    out = await compute_for_line(db_session, profile_id=p.id, subtotal=Decimal("500"))
    assert out[0].amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_unknown_profile_returns_empty(db_session):
    import uuid as _uuid
    out = await compute_for_line(db_session, profile_id=_uuid.uuid4(), subtotal=Decimal("100"))
    assert out == []


@pytest.mark.asyncio
async def test_compound_three_layers_ordering(db_session):
    p = TaxProfile(name="3-layer", jurisdiction="X", tax_rate=Decimal("0"), is_compound=True)
    db_session.add(p)
    await db_session.flush()
    db_session.add(TaxProfileComponent(profile_id=p.id, name="A", rate=Decimal("10"), apply_order=0))
    db_session.add(TaxProfileComponent(profile_id=p.id, name="B", rate=Decimal("10"), apply_order=1))
    db_session.add(TaxProfileComponent(profile_id=p.id, name="C", rate=Decimal("10"), apply_order=2))
    await db_session.flush()

    out = await compute_for_line(db_session, profile_id=p.id, subtotal=Decimal("100"))
    assert out[0].amount == Decimal("10.00")  # 100 * 10
    assert out[1].amount == Decimal("11.00")  # 110 * 10
    assert out[2].amount == Decimal("12.10")  # 121 * 10
