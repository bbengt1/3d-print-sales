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
        if not components:
            # #283 P1: a compound profile with no components must fail fast
            # rather than silently returning [] — otherwise downstream tax
            # posting skips tax entirely during partial setup, producing an
            # under-collection bug.
            raise ValueError(
                f"Compound tax profile {profile.id} ({profile.name!r}) "
                "has no components configured"
            )
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


# ---------- #329 P2: per-component remittance breakdown ----------


@dataclass
class ComponentBreakdownRow:
    profile_id: uuid.UUID
    profile_name: str
    component_name: str
    rate: Decimal
    sales_subtotal: Decimal
    estimated_tax: Decimal


async def compute_component_breakdown(
    db: AsyncSession,
    *,
    profile_id: uuid.UUID,
    sales_subtotal: Decimal,
) -> list[ComponentBreakdownRow]:
    """Decomposes the per-period total `sales_subtotal` for a single profile
    across its components. For single-rate profiles returns one row.

    The result is the **estimated** tax — the actual `Sale.tax_collected`
    column may differ if components were stacked compound-style at the time
    of sale, since we don't store the per-component split per-sale today.
    For seller-collected single-rate or non-compound profiles, the estimate
    is the actual.
    """
    rows = await compute_for_line(db, profile_id=profile_id, subtotal=sales_subtotal)
    if not rows:
        return []
    profile = (
        await db.execute(select(TaxProfile).where(TaxProfile.id == profile_id))
    ).scalar_one()
    return [
        ComponentBreakdownRow(
            profile_id=profile.id,
            profile_name=profile.name,
            component_name=r.component_name,
            rate=r.rate,
            sales_subtotal=Decimal(sales_subtotal),
            estimated_tax=r.amount,
        )
        for r in rows
    ]
