"""Fixed asset register lifecycle (#238).

Operations:
- create / edit a fixed asset (with edit-lock once depreciation has been posted)
- post depreciation for a single asset, or in bulk for all active assets,
  through a chosen `period_end` date (idempotent — re-posting through the
  same period is a no-op).
- dispose an asset: post any pending depreciation up through `disposed_on`,
  then post a disposal JE (Cr asset, Dr accumulated, Dr/Cr cash for proceeds,
  Dr loss / Cr gain for the residual).
- compute book value for any asset at any point in time.

Math:
- straight_line: monthly = (cost - salvage) / life_months. Last month rounds
  to bring book value exactly to salvage.
- declining_balance: monthly = book_value_start_of_period × rate / 12, where
  `rate` defaults to 2 / life_years (DDB) when not explicitly set. We switch
  to straight-line over the remaining life when SL would yield a larger
  monthly amount, ensuring the asset reaches salvage by end of life.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_period import AccountingPeriod
from app.models.fixed_asset import DepreciationEntry, FixedAsset
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
)


class FixedAssetError(RuntimeError):
    pass


CENTS = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def _last_day_of_month(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _add_months(d: date, n: int) -> date:
    """Return last-day-of-month n months after `d`."""
    total = d.year * 12 + (d.month - 1) + n
    y, m = divmod(total, 12)
    return _last_day_of_month(date(y, m + 1, 1))


def _months_between(start: date, end: date) -> int:
    """Inclusive count of month-ends between start (the month-end of acquisition month)
    and end (a chosen month-end). Returns 0 if end < start."""
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


async def compute_book_value(db: AsyncSession, asset_id: uuid.UUID) -> Decimal:
    asset = (await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise FixedAssetError("Fixed asset not found")
    posted = (
        await db.execute(
            select(DepreciationEntry).where(DepreciationEntry.fixed_asset_id == asset_id)
        )
    ).scalars().all()
    accum = sum((Decimal(e.amount) for e in posted), Decimal("0"))
    return _q(Decimal(asset.acquisition_cost) - accum)


def _ddb_rate_default(life_months: int) -> Decimal:
    """Double-declining-balance rate as an annual fraction."""
    life_years = Decimal(life_months) / Decimal(12)
    return Decimal(2) / life_years


def _planned_monthly_amount_sl(asset: FixedAsset) -> Decimal:
    cost = Decimal(asset.acquisition_cost)
    salvage = Decimal(asset.salvage_value or 0)
    return _q((cost - salvage) / Decimal(asset.useful_life_months))


def _planned_amounts_db(asset: FixedAsset) -> list[Decimal]:
    """Generate the full per-period amount schedule for a declining-balance
    asset across its full useful life, switching to straight-line whenever SL
    would yield a larger monthly amount over the remaining life. Returns a
    list of length `useful_life_months` summing exactly to (cost - salvage).
    """
    cost = Decimal(asset.acquisition_cost)
    salvage = Decimal(asset.salvage_value or 0)
    life = int(asset.useful_life_months)
    rate_annual = (
        Decimal(asset.declining_balance_rate)
        if asset.declining_balance_rate is not None
        else _ddb_rate_default(life)
    )

    monthly_rate = rate_annual / Decimal(12)
    amounts: list[Decimal] = []
    book = cost
    for i in range(life):
        remaining_months = life - i
        # SL on the residual to-salvage from this period forward
        sl = _q((book - salvage) / Decimal(remaining_months))
        db_amt = _q(book * monthly_rate)
        amt = max(sl, db_amt)
        # Don't depreciate below salvage
        amt = min(amt, _q(book - salvage))
        amounts.append(amt)
        book -= amt
    # Force final-period adjustment so the schedule sums to exactly (cost - salvage)
    target = _q(cost - salvage)
    diff = target - sum(amounts, Decimal("0"))
    amounts[-1] = _q(amounts[-1] + diff)
    return amounts


def _planned_amounts_sl(asset: FixedAsset) -> list[Decimal]:
    cost = Decimal(asset.acquisition_cost)
    salvage = Decimal(asset.salvage_value or 0)
    life = int(asset.useful_life_months)
    monthly = _planned_monthly_amount_sl(asset)
    amounts = [monthly] * life
    target = _q(cost - salvage)
    diff = target - sum(amounts, Decimal("0"))
    amounts[-1] = _q(amounts[-1] + diff)
    return amounts


def planned_schedule(asset: FixedAsset) -> list[tuple[date, Decimal]]:
    """Return [(period_end, amount)] schedule across the full useful life.
    `period_end` is the last day of each successive month after acquisition.
    """
    if asset.depreciation_method == "declining_balance":
        amounts = _planned_amounts_db(asset)
    else:
        amounts = _planned_amounts_sl(asset)

    first_period = _last_day_of_month(asset.acquired_on)
    out = []
    for i, amt in enumerate(amounts):
        period_end = _add_months(first_period, i)
        out.append((period_end, amt))
    return out


async def post_depreciation(
    db: AsyncSession,
    *,
    asset_id: uuid.UUID,
    through: date,
) -> list[DepreciationEntry]:
    """Post any unposted depreciation entries up through the given `through`
    month-end. Idempotent: existing `(asset, period_end)` rows are skipped.
    """
    asset = (await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise FixedAssetError("Fixed asset not found")
    if asset.status == "disposed":
        raise FixedAssetError("Cannot post depreciation on a disposed asset")

    schedule = planned_schedule(asset)
    posted_periods = set(
        (
            await db.execute(
                select(DepreciationEntry.period_end).where(
                    DepreciationEntry.fixed_asset_id == asset_id
                )
            )
        ).scalars().all()
    )

    new_entries: list[DepreciationEntry] = []
    for period_end, amount in schedule:
        if period_end > through:
            break
        if period_end in posted_periods:
            continue
        if amount <= 0:
            continue

        # Period-lock guard: refuse if the target month is in a closed period.
        # If no AccountingPeriod row covers this date we treat it as open.
        period_row = (
            await db.execute(
                select(AccountingPeriod).where(
                    AccountingPeriod.start_date <= period_end,
                    AccountingPeriod.end_date >= period_end,
                )
            )
        ).scalar_one_or_none()
        if period_row is not None and period_row.status != "open":
            raise FixedAssetError(
                f"Accounting period containing {period_end.isoformat()} is closed; "
                f"cannot post depreciation"
            )

        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=period_end,
                accounting_period_id=period_row.id if period_row else None,
                source_type="depreciation",
                source_id=str(asset.id),
                memo=f"Depreciation for {asset.name} — {period_end.isoformat()}",
                lines=[
                    JournalLineCreate(
                        account_id=asset.depreciation_expense_account_id,
                        entry_type="debit",
                        amount=amount,
                        description=f"Depreciation Expense — {asset.name}",
                    ),
                    JournalLineCreate(
                        account_id=asset.accumulated_depreciation_account_id,
                        entry_type="credit",
                        amount=amount,
                        description=f"Accum. Depreciation — {asset.name}",
                    ),
                ],
            ),
        )
        de = DepreciationEntry(
            fixed_asset_id=asset.id,
            period_end=period_end,
            amount=amount,
            journal_entry_id=entry.id,
        )
        db.add(de)
        new_entries.append(de)

    # Auto-flip status to fully_depreciated when book value reaches salvage
    book = await compute_book_value(db, asset.id)
    if book <= Decimal(asset.salvage_value or 0) and asset.status == "active":
        asset.status = "fully_depreciated"

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
) -> FixedAsset:
    """Post the disposal JE for an asset:
        Cr Equipment (full acquisition cost)
        Dr Accumulated Depreciation (full accumulated balance)
        Dr Cash/AR (if proceeds > 0)
        Dr Loss on Disposal OR Cr Gain on Disposal for the residual.
    Posts pending depreciation through `disposed_on` first.
    """
    asset = (await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise FixedAssetError("Fixed asset not found")
    if asset.status == "disposed":
        raise FixedAssetError("Asset is already disposed")

    proceeds = Decimal(proceeds or 0)
    if proceeds < 0:
        raise FixedAssetError("Disposal proceeds must be non-negative")
    if proceeds > 0 and proceeds_account_id is None:
        raise FixedAssetError("proceeds_account_id required when proceeds > 0")

    # Post pending depreciation first
    await post_depreciation(db, asset_id=asset.id, through=disposed_on)

    posted_total = Decimal("0")
    for e in (
        await db.execute(
            select(DepreciationEntry).where(DepreciationEntry.fixed_asset_id == asset.id)
        )
    ).scalars().all():
        posted_total += Decimal(e.amount)

    cost = Decimal(asset.acquisition_cost)
    book_value = _q(cost - posted_total)
    accumulated = _q(posted_total)
    proceeds_q = _q(proceeds)

    # Gain/loss = proceeds - book_value
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
                account_id=asset.accumulated_depreciation_account_id,
                entry_type="debit",
                amount=accumulated,
                description=f"Dispose {asset.name} — accumulated depreciation",
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
        # Gain
        lines.append(
            JournalLineCreate(
                account_id=gain_account_id,
                entry_type="credit",
                amount=delta,
                description=f"Gain on disposal of {asset.name}",
            )
        )
    elif delta < 0:
        # Loss
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
        raise FixedAssetError("Accounting period for disposal date is closed")

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=disposed_on,
                accounting_period_id=period_row.id if period_row else None,
                source_type="fixed_asset_disposal",
                source_id=str(asset.id),
                memo=f"Disposal of {asset.name}",
                lines=lines,
            ),
        )
    except AccountingValidationError as e:
        raise FixedAssetError(str(e)) from e

    asset.status = "disposed"
    asset.disposed_on = disposed_on
    asset.disposal_proceeds = proceeds_q if proceeds_q > 0 else None
    asset.disposal_journal_entry_id = entry.id

    # If a printer is linked, mark inactive — preserve printer history.
    from app.models.printer import Printer
    printers = (
        await db.execute(select(Printer).where(Printer.fixed_asset_id == asset.id))
    ).scalars().all()
    for p in printers:
        p.is_active = False

    await db.flush()
    return asset


async def can_edit_critical_fields(db: AsyncSession, asset_id: uuid.UUID) -> bool:
    """Cost/method/life are immutable once any depreciation has been posted."""
    posted = (
        await db.execute(
            select(DepreciationEntry).where(DepreciationEntry.fixed_asset_id == asset_id).limit(1)
        )
    ).scalar_one_or_none()
    return posted is None
