"""Regression: Codex P1 on PR #283.

A compound tax profile with no `tax_profile_components` rows must fail
fast — silently returning `[]` causes downstream tax posting to skip
tax entirely, producing an under-collection bug during partial setup.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.tax_profile import TaxProfile, TaxProfileComponent
from app.services.tax_service import compute_for_line


@pytest.mark.asyncio
async def test_compound_profile_with_no_components_raises(db_session):
    p = TaxProfile(
        name="Compound (no components)",
        jurisdiction="X",
        tax_rate=Decimal("0"),
        is_compound=True,
    )
    db_session.add(p)
    await db_session.flush()

    with pytest.raises(ValueError, match="no components"):
        await compute_for_line(
            db_session, profile_id=p.id, subtotal=Decimal("100")
        )


@pytest.mark.asyncio
async def test_compound_profile_with_components_still_works(db_session):
    """Positive case: a normally-configured compound profile is unaffected."""
    p = TaxProfile(
        name="Compound (with components)",
        jurisdiction="X",
        tax_rate=Decimal("0"),
        is_compound=True,
    )
    db_session.add(p)
    await db_session.flush()
    db_session.add(
        TaxProfileComponent(
            profile_id=p.id, name="A", rate=Decimal("5.000"), apply_order=0
        )
    )
    db_session.add(
        TaxProfileComponent(
            profile_id=p.id, name="B", rate=Decimal("9.975"), apply_order=1
        )
    )
    await db_session.flush()

    out = await compute_for_line(
        db_session, profile_id=p.id, subtotal=Decimal("100")
    )
    assert len(out) == 2
    assert out[0].amount == Decimal("5.00")
    assert out[1].amount == Decimal("10.47")
