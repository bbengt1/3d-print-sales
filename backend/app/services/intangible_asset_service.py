"""Intangible asset register lifecycle (#252).

Symmetric mirror of fixed_asset_service. Same straight-line and
declining-balance math, same idempotent post-through-period semantics,
same disposal flow with gain/loss accounting. Different field names
(amortization vs depreciation) and different default COA accounts.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_period import AccountingPeriod
from app.models.intangible_asset import AmortizationEntry, IntangibleAsset
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
)


class IntangibleAssetError(RuntimeError):
    pass


CENTS = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def _last_day_of_month(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _add_months(d: date, n: int) -> date:
    total = d.year * 12 + (d.month - 1) + n
    y, m = divmod(total, 12)
    return _last_day_of_month(date(y, m + 1, 1))


def _planned_amounts_sl(asset: IntangibleAsset) -> list[Decimal]:
    cost = Decimal(asset.acquisition_cost)
    salvage = Decimal(asset.salvage_value or 0)
    life = int(asset.useful_life_months)
    monthly = _q((cost - salvage) / Decimal(life))
    amounts = [monthly] * life
    target = _q(cost - salvage)
    diff = target - sum(amounts, Decimal("0"))
    amounts[-1] = _q(amounts[-1] + diff)
    return amounts


def _planned_amounts_db(asset: IntangibleAsset) -> list[Decimal]:
    cost = Decimal(asset.acquisition_cost)
    salvage = Decimal(asset.salvage_value or 0)
    life = int(asset.useful_life_months)
    rate_annual = (
        Decimal(asset.declining_balance_rate)
        if asset.declining_balance_rate is not None
        else Decimal(2) / (Decimal(life) / Decimal(12))
    )
    monthly_rate = rate_annual / Decimal(12)
    amounts: list[Decimal] = []
    book = cost
    for i in range(life):
        remaining_months = life - i
        sl = _q((book - salvage) / Decimal(remaining_months))
        db_amt = _q(book * monthly_rate)
        amt = max(sl, db_amt)
        amt = min(amt, _q(book - salvage))
        amounts.append(amt)
        book -= amt
    target = _q(cost - salvage)
    diff = target - sum(amounts, Decimal("0"))
    amounts[-1] = _q(amounts[-1] + diff)
    return amounts


def planned_schedule(asset: IntangibleAsset) -> list[tuple[date, Decimal]]:
    if asset.amortization_method == "declining_balance":
        amounts = _planned_amounts_db(asset)
    else:
        amounts = _planned_amounts_sl(asset)
    first_period = _last_day_of_month(asset.acquired_on)
    out = []
    for i, amt in enumerate(amounts):
        out.append((_add_months(first_period, i), amt))
    return out


async def compute_book_value(db: AsyncSession, asset_id: uuid.UUID) -> Decimal:
    asset = (await db.execute(select(IntangibleAsset).where(IntangibleAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise IntangibleAssetError("Intangible asset not found")
    posted = (
        await db.execute(
            select(AmortizationEntry).where(AmortizationEntry.intangible_asset_id == asset_id)
        )
    ).scalars().all()
    accum = sum((Decimal(e.amount) for e in posted), Decimal("0"))
    return _q(Decimal(asset.acquisition_cost) - accum)


async def post_amortization(
    db: AsyncSession,
    *,
    asset_id: uuid.UUID,
    through: date,
) -> list[AmortizationEntry]:
    asset = (await db.execute(select(IntangibleAsset).where(IntangibleAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise IntangibleAssetError("Intangible asset not found")
    if asset.status == "disposed":
        raise IntangibleAssetError("Cannot post amortization on a disposed asset")

    schedule = planned_schedule(asset)
    posted_periods = set(
        (
            await db.execute(
                select(AmortizationEntry.period_end).where(
                    AmortizationEntry.intangible_asset_id == asset_id
                )
            )
        ).scalars().all()
    )

    # #279 Codex P1: `create_journal_entry` commits each call immediately, so
    # any per-month validation failure mid-loop would persist earlier months
    # and leave the asset partially amortized. Pre-validate every month's
    # closed-period guard up front so the whole post is all-or-nothing
    # (mirrors the PR #273 fix in `fixed_asset_service.post_depreciation`).
    months_to_post: list[tuple[date, Decimal, AccountingPeriod | None]] = []
    for period_end, amount in schedule:
        if period_end > through:
            break
        if period_end in posted_periods:
            continue
        if amount <= 0:
            continue

        period_row = (
            await db.execute(
                select(AccountingPeriod).where(
                    AccountingPeriod.start_date <= period_end,
                    AccountingPeriod.end_date >= period_end,
                )
            )
        ).scalar_one_or_none()
        if period_row is not None and period_row.status != "open":
            raise IntangibleAssetError(
                f"Accounting period containing {period_end.isoformat()} is closed"
            )
        months_to_post.append((period_end, amount, period_row))

    new_entries: list[AmortizationEntry] = []
    for period_end, amount, period_row in months_to_post:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=period_end,
                accounting_period_id=period_row.id if period_row else None,
                source_type="amortization",
                source_id=str(asset.id),
                memo=f"Amortization for {asset.name} — {period_end.isoformat()}",
                lines=[
                    JournalLineCreate(
                        account_id=asset.amortization_expense_account_id,
                        entry_type="debit",
                        amount=amount,
                        description=f"Amortization Expense — {asset.name}",
                    ),
                    JournalLineCreate(
                        account_id=asset.accumulated_amortization_account_id,
                        entry_type="credit",
                        amount=amount,
                        description=f"Accum. Amortization — {asset.name}",
                    ),
                ],
            ),
        )
        ae = AmortizationEntry(
            intangible_asset_id=asset.id,
            period_end=period_end,
            amount=amount,
            journal_entry_id=entry.id,
        )
        db.add(ae)
        new_entries.append(ae)

    book = await compute_book_value(db, asset.id)
    if book <= Decimal(asset.salvage_value or 0) and asset.status == "active":
        asset.status = "fully_amortized"

    await db.flush()
    return new_entries


async def dispose_asset(
    db: AsyncSession,
    *,
    asset_id: uuid.UUID,
    disposed_on: date,
    proceeds: Decimal | None,
    proceeds_account_id: uuid.UUID | None,
    gain_account_id: uuid.UUID,
    loss_account_id: uuid.UUID,
) -> IntangibleAsset:
    asset = (await db.execute(select(IntangibleAsset).where(IntangibleAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise IntangibleAssetError("Intangible asset not found")
    if asset.status == "disposed":
        raise IntangibleAssetError("Asset is already disposed")

    # #279 Codex P1: a disposal date earlier than the acquisition date would
    # produce an impossible asset lifecycle (and a JE that predates the
    # asset's existence). Guard up front so we never reach `post_amortization`
    # or the disposal JE write with an inverted date pair.
    if disposed_on < asset.acquired_on:
        raise IntangibleAssetError(
            f"Disposal date {disposed_on.isoformat()} cannot be before "
            f"acquisition date {asset.acquired_on.isoformat()}"
        )

    proceeds = Decimal(proceeds or 0)
    if proceeds < 0:
        raise IntangibleAssetError("Disposal proceeds must be non-negative")
    if proceeds > 0 and proceeds_account_id is None:
        raise IntangibleAssetError("proceeds_account_id required when proceeds > 0")

    await post_amortization(db, asset_id=asset.id, through=disposed_on)

    posted_total = Decimal("0")
    for e in (
        await db.execute(
            select(AmortizationEntry).where(AmortizationEntry.intangible_asset_id == asset.id)
        )
    ).scalars().all():
        posted_total += Decimal(e.amount)

    cost = Decimal(asset.acquisition_cost)
    book_value = _q(cost - posted_total)
    accumulated = _q(posted_total)
    proceeds_q = _q(proceeds)
    delta = _q(proceeds_q - book_value)

    lines = [
        JournalLineCreate(
            account_id=asset.asset_account_id,
            entry_type="credit",
            amount=cost,
            description=f"Dispose {asset.name} — original cost",
        ),
    ]
    if accumulated > 0:
        lines.append(
            JournalLineCreate(
                account_id=asset.accumulated_amortization_account_id,
                entry_type="debit",
                amount=accumulated,
                description=f"Dispose {asset.name} — accumulated amortization",
            )
        )
    if proceeds_q > 0:
        assert proceeds_account_id is not None
        lines.append(
            JournalLineCreate(
                account_id=proceeds_account_id,
                entry_type="debit",
                amount=proceeds_q,
                description=f"Dispose {asset.name} — proceeds",
            )
        )
    if delta > 0:
        lines.append(
            JournalLineCreate(
                account_id=gain_account_id,
                entry_type="credit",
                amount=delta,
                description=f"Gain on disposal of {asset.name}",
            )
        )
    elif delta < 0:
        lines.append(
            JournalLineCreate(
                account_id=loss_account_id,
                entry_type="debit",
                amount=-delta,
                description=f"Loss on disposal of {asset.name}",
            )
        )

    period_row = (
        await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.start_date <= disposed_on,
                AccountingPeriod.end_date >= disposed_on,
            )
        )
    ).scalar_one_or_none()
    if period_row is not None and period_row.status != "open":
        raise IntangibleAssetError("Accounting period for disposal date is closed")

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=disposed_on,
                accounting_period_id=period_row.id if period_row else None,
                source_type="intangible_asset_disposal",
                source_id=str(asset.id),
                memo=f"Disposal of {asset.name}",
                lines=lines,
            ),
        )
    except AccountingValidationError as e:
        raise IntangibleAssetError(str(e)) from e

    asset.status = "disposed"
    asset.disposed_on = disposed_on
    asset.disposal_proceeds = proceeds_q if proceeds_q > 0 else None
    asset.disposal_journal_entry_id = entry.id
    await db.flush()
    return asset


async def can_edit_critical_fields(db: AsyncSession, asset_id: uuid.UUID) -> bool:
    posted = (
        await db.execute(
            select(AmortizationEntry).where(AmortizationEntry.intangible_asset_id == asset_id).limit(1)
        )
    ).scalar_one_or_none()
    return posted is None
