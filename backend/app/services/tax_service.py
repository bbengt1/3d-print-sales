"""Tax-profile computation (#258).

`compute_for_line` returns one or more `(component_name, base, rate, amount, account_id)`
tuples for a given subtotal and profile. A single-rate profile returns one
tuple. A compound profile returns one per component, each layer applied to
`base + sum_of_prior_amounts`. A reverse-charge profile returns the same
tuples but the caller is expected to post both a payable and a receivable
JE leg of the same magnitude.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tax_profile import TaxProfile, TaxProfileComponent


CENTS = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass
class TaxComputation:
    component_name: str
    base: Decimal
    rate: Decimal  # percent — e.g. 7.000 for 7%
    amount: Decimal
    account_id: uuid.UUID | None
    is_reverse_charge: bool = False


async def compute_for_line(
    db: AsyncSession, *, profile_id: uuid.UUID, subtotal: Decimal
) -> list[TaxComputation]:
    profile = (
        await db.execute(select(TaxProfile).where(TaxProfile.id == profile_id))
    ).scalar_one_or_none()
    if profile is None:
        return []

    base = _q(Decimal(subtotal))
    out: list[TaxComputation] = []

    if profile.is_compound:
        components = (
            await db.execute(
                select(TaxProfileComponent)
                .where(TaxProfileComponent.profile_id == profile.id)
                .order_by(TaxProfileComponent.apply_order)
            )
        ).scalars().all()
        running = base
        for c in components:
            amt = _q(running * Decimal(c.rate) / Decimal(100))
            out.append(
                TaxComputation(
                    component_name=c.name,
                    base=running,
                    rate=Decimal(c.rate),
                    amount=amt,
                    account_id=c.liability_account_id,
                    is_reverse_charge=profile.is_reverse_charge,
                )
            )
            running += amt  # next layer applies to base + sum of prior taxes
    else:
        amt = _q(base * Decimal(profile.tax_rate) / Decimal(100))
        out.append(
            TaxComputation(
                component_name=profile.name,
                base=base,
                rate=Decimal(profile.tax_rate),
                amount=amt,
                account_id=None,
                is_reverse_charge=profile.is_reverse_charge,
            )
        )

    return out
