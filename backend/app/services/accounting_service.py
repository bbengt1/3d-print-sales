from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.accounting import JournalEntryCreate, JournalEntryReverse

STARTER_CHART_OF_ACCOUNTS = [
    ("1000", "Cash", "asset", "debit"),
    ("1100", "Accounts Receivable", "asset", "debit"),
    ("1200", "Raw Materials Inventory", "asset", "debit"),
    ("1300", "Work In Progress Inventory", "asset", "debit"),
    ("1400", "Finished Goods Inventory", "asset", "debit"),
    ("1500", "Prepaid Expenses", "asset", "debit"),
    ("2000", "Accounts Payable", "liability", "credit"),
    ("2100", "Sales Tax Payable", "liability", "credit"),
    ("2200", "Deferred Revenue", "liability", "credit"),
    ("3000", "Owner Equity", "equity", "credit"),
    ("3100", "Owner Draws", "equity", "debit"),
    ("3200", "Retained Earnings", "equity", "credit"),
    ("4000", "Product Sales", "revenue", "credit"),
    ("4100", "Shipping Income", "revenue", "credit"),
    ("4900", "Other Income", "revenue", "credit"),
    ("5000", "Material COGS", "cogs", "debit"),
    ("5100", "Labor COGS", "cogs", "debit"),
    ("5200", "Machine COGS", "cogs", "debit"),
    ("5300", "Packaging & Fulfillment", "cogs", "debit"),
    ("6000", "Marketplace Fees", "expense", "debit"),
    ("6100", "Software & Subscriptions", "expense", "debit"),
    ("6200", "Advertising", "expense", "debit"),
    ("6300", "Repairs & Maintenance", "expense", "debit"),
    ("6400", "Utilities", "expense", "debit"),
    ("6500", "Office & Supplies", "expense", "debit"),
]


class AccountingValidationError(ValueError):
    pass


def _validate_open_period(period: AccountingPeriod | None) -> None:
    if period and period.status != "open":
        raise AccountingValidationError("Cannot post journal entry to a non-open accounting period.")


def _validate_period_editable(period: AccountingPeriod) -> None:
    if period.status == "locked":
        raise AccountingValidationError("Locked accounting periods cannot be edited.")


async def seed_chart_of_accounts(db: AsyncSession) -> None:
    result = await db.execute(select(Account).limit(1))
    if result.scalar_one_or_none():
        return

    for code, name, account_type, normal_balance in STARTER_CHART_OF_ACCOUNTS:
        db.add(
            Account(
                code=code,
                name=name,
                account_type=account_type,
                normal_balance=normal_balance,
                is_system=True,
            )
        )
    await db.commit()


async def ensure_accounting_period(
    db: AsyncSession,
    *,
    period_key: str,
    name: str,
    start_date,
    end_date,
    status: str = "open",
) -> AccountingPeriod:
    result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.period_key == period_key)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    period = AccountingPeriod(
        period_key=period_key,
        name=name,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period


async def create_journal_entry(db: AsyncSession, payload: JournalEntryCreate) -> JournalEntry:
    if not payload.lines or len(payload.lines) < 2:
        raise AccountingValidationError("Journal entries require at least two lines.")

    debit_total = sum((line.amount for line in payload.lines if line.entry_type == "debit"), Decimal("0"))
    credit_total = sum((line.amount for line in payload.lines if line.entry_type == "credit"), Decimal("0"))

    if debit_total != credit_total:
        raise AccountingValidationError("Journal entry is unbalanced: debits must equal credits.")

    account_ids = [line.account_id for line in payload.lines]
    result = await db.execute(select(Account).where(Account.id.in_(account_ids)))
    accounts = {acct.id: acct for acct in result.scalars().all()}
    missing = [str(account_id) for account_id in account_ids if account_id not in accounts]
    if missing:
        raise AccountingValidationError(f"Journal entry references missing accounts: {', '.join(missing)}")

    if payload.accounting_period_id:
        period_result = await db.execute(
            select(AccountingPeriod).where(AccountingPeriod.id == payload.accounting_period_id)
        )
        period = period_result.scalar_one_or_none()
        if not period:
            raise AccountingValidationError("Accounting period not found.")
        _validate_open_period(period)

    count_result = await db.execute(select(JournalEntry))
    next_number = len(count_result.scalars().all()) + 1
    entry = JournalEntry(
        entry_number=f"JE-{payload.entry_date.year}-{next_number:04d}",
        entry_date=payload.entry_date,
        accounting_period_id=payload.accounting_period_id,
        status="posted",
        source_type=payload.source_type,
        source_id=payload.source_id,
        memo=payload.memo,
        posted_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()

    for index, line in enumerate(payload.lines, start=1):
        db.add(
            JournalLine(
                journal_entry_id=entry.id,
                account_id=line.account_id,
                line_number=index,
                entry_type=line.entry_type,
                amount=line.amount,
                description=line.description,
            )
        )

    await db.commit()
    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry.id)
    )
    return result.scalar_one()


async def set_accounting_period_status(
    db: AsyncSession,
    *,
    period_id,
    status: str,
) -> AccountingPeriod:
    result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id)
    )
    period = result.scalar_one_or_none()
    if not period:
        raise AccountingValidationError("Accounting period not found.")

    if period.status == "locked" and status != "locked":
        raise AccountingValidationError("Locked accounting periods cannot be reopened or modified.")

    period.status = status
    await db.commit()
    await db.refresh(period)
    return period


async def reverse_journal_entry(
    db: AsyncSession,
    *,
    entry_id,
    payload: JournalEntryReverse,
) -> JournalEntry:
    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise AccountingValidationError("Journal entry not found.")
    if entry.status != "posted":
        raise AccountingValidationError("Only posted journal entries can be reversed.")
    if entry.is_reversal:
        raise AccountingValidationError("Reversal entries cannot be reversed again.")

    existing_reversal = await db.execute(
        select(JournalEntry).where(JournalEntry.reversal_of_id == entry.id)
    )
    if existing_reversal.scalar_one_or_none():
        raise AccountingValidationError("Journal entry has already been reversed.")

    reversal_period = None
    if entry.accounting_period_id:
        period_result = await db.execute(
            select(AccountingPeriod).where(AccountingPeriod.id == entry.accounting_period_id)
        )
        original_period = period_result.scalar_one_or_none()
        if original_period and original_period.start_date <= payload.reversal_date <= original_period.end_date:
            reversal_period = original_period
            _validate_open_period(reversal_period)

    count_result = await db.execute(select(JournalEntry))
    next_number = len(count_result.scalars().all()) + 1
    reversal_entry = JournalEntry(
        entry_number=f"JE-{payload.reversal_date.year}-{next_number:04d}",
        entry_date=payload.reversal_date,
        accounting_period_id=reversal_period.id if reversal_period else None,
        status="posted",
        source_type=entry.source_type,
        source_id=entry.source_id,
        memo=payload.memo or f"Reversal of {entry.entry_number}",
        posted_at=datetime.now(timezone.utc),
        is_reversal=True,
        reversal_of_id=entry.id,
    )
    db.add(reversal_entry)
    await db.flush()

    for index, line in enumerate(entry.lines, start=1):
        opposite = "credit" if line.entry_type == "debit" else "debit"
        db.add(
            JournalLine(
                journal_entry_id=reversal_entry.id,
                account_id=line.account_id,
                line_number=index,
                entry_type=opposite,
                amount=line.amount,
                description=line.description,
            )
        )

    await db.commit()
    refreshed = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == reversal_entry.id)
    )
    return refreshed.scalar_one()
