"""Accounting foundations cluster (#260):

1. RecurringJournalEntry lifecycle (mirrors recurring_invoice_service)
2. Suspense report (drill-down on account 1900 balance)
3. Starting balances workflow (admin posts a single migration JE)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.recurring_journal_entry import (
    RecurringJournalEntry,
    RecurringJournalEntryRun,
)
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
)
from app.services.recurring_invoice_service import advance_date


class AccountingFoundationsError(RuntimeError):
    pass


# ---------- RecurringJournalEntry lifecycle ----------


async def run_one_je(
    db: AsyncSession,
    *,
    recurring_id: uuid.UUID,
    triggered_by: str = "manual_run_now",
) -> RecurringJournalEntryRun:
    rje = (
        await db.execute(
            select(RecurringJournalEntry).where(RecurringJournalEntry.id == recurring_id)
        )
    ).scalar_one_or_none()
    if rje is None:
        raise AccountingFoundationsError("Recurring JE not found")
    if not rje.is_active:
        raise AccountingFoundationsError("Recurring JE is paused")

    target_date = rje.next_run_on
    try:
        je = await _generate_je(db, rje, target_date)
    except Exception as e:  # noqa: BLE001
        rje.last_error = f"{type(e).__name__}: {e}"
        rje.last_failed_at = datetime.now(timezone.utc)
        run = RecurringJournalEntryRun(
            recurring_je_id=rje.id,
            target_date=target_date,
            status="failed",
            error=rje.last_error,
            triggered_by=triggered_by,
        )
        db.add(run)
        await db.flush()
        return run

    next_due = advance_date(target_date, rje.cadence, rje.interval_count)
    rje.last_run_on = target_date
    rje.next_run_on = next_due
    rje.last_error = None
    rje.last_failed_at = None
    if rje.end_on is not None and next_due > rje.end_on:
        rje.is_active = False

    run = RecurringJournalEntryRun(
        recurring_je_id=rje.id,
        target_date=target_date,
        status="succeeded",
        generated_journal_entry_id=je.id,
        triggered_by=triggered_by,
    )
    db.add(run)
    await db.flush()
    return run


async def skip_next_je(db: AsyncSession, recurring_id: uuid.UUID) -> RecurringJournalEntryRun:
    rje = (
        await db.execute(
            select(RecurringJournalEntry).where(RecurringJournalEntry.id == recurring_id)
        )
    ).scalar_one_or_none()
    if rje is None:
        raise AccountingFoundationsError("Recurring JE not found")
    target_date = rje.next_run_on
    next_due = advance_date(target_date, rje.cadence, rje.interval_count)
    rje.last_run_on = target_date
    rje.next_run_on = next_due
    if rje.end_on is not None and next_due > rje.end_on:
        rje.is_active = False
    run = RecurringJournalEntryRun(
        recurring_je_id=rje.id,
        target_date=target_date,
        status="skipped",
        triggered_by="manual_skip",
    )
    db.add(run)
    await db.flush()
    return run


async def run_due_jes(db: AsyncSession, *, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    rules = (
        await db.execute(
            select(RecurringJournalEntry).where(
                RecurringJournalEntry.is_active == True,  # noqa: E712
                RecurringJournalEntry.next_run_on <= today,
            )
        )
    ).scalars().all()

    succeeded = failed = 0
    for r in rules:
        run = await run_one_je(db, recurring_id=r.id, triggered_by="cron")
        if run.status == "succeeded":
            succeeded += 1
        else:
            failed += 1
    return {"considered": len(rules), "succeeded": succeeded, "failed": failed}


async def _generate_je(
    db: AsyncSession, rje: RecurringJournalEntry, entry_date: date
) -> JournalEntry:
    template = list(rje.lines_template or [])
    if not template or len(template) < 2:
        raise AccountingFoundationsError("Template must have at least two lines")

    je_lines = [
        JournalLineCreate(
            account_id=line["account_id"],
            entry_type=line["entry_type"],
            amount=Decimal(str(line["amount"])),
            description=line.get("description"),
        )
        for line in template
    ]
    return await create_journal_entry(
        db,
        JournalEntryCreate(
            entry_date=entry_date,
            source_type="recurring_journal_entry",
            source_id=str(rje.id),
            memo=rje.memo or rje.name,
            lines=je_lines,
        ),
    )


# ---------- Suspense report ----------


async def suspense_report(db: AsyncSession) -> dict:
    """Returns balance + open journal lines posting to the Suspense account
    (code 1900). Operators reclassify by editing the source transactions.
    """
    suspense = (
        await db.execute(select(Account).where(Account.code == "1900"))
    ).scalar_one_or_none()
    if suspense is None:
        return {
            "configured": False,
            "balance": Decimal("0"),
            "lines": [],
        }

    rows = (
        await db.execute(
            select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalLine.account_id == suspense.id)
            .order_by(JournalEntry.entry_date.desc(), JournalLine.line_number)
        )
    ).all()

    balance = Decimal("0")
    out_lines = []
    for line, entry in rows:
        sign = 1 if line.entry_type == "debit" else -1
        balance += Decimal(line.amount) * sign
        out_lines.append(
            {
                "journal_line_id": str(line.id),
                "journal_entry_id": str(entry.id),
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date.isoformat(),
                "entry_type": line.entry_type,
                "amount": str(Decimal(line.amount)),
                "description": line.description,
                "source_type": entry.source_type,
                "source_id": entry.source_id,
                "memo": entry.memo,
            }
        )
    return {
        "configured": True,
        "account_id": str(suspense.id),
        "balance": str(balance.quantize(Decimal("0.01"))),
        "lines": out_lines,
    }


# ---------- Starting balances ----------


async def post_starting_balances(
    db: AsyncSession,
    *,
    as_of: date,
    balances: list[dict],
    force: bool = False,
) -> JournalEntry:
    """Post a single 'opening balance' JE that brings each named account to
    the requested starting balance. The balancing entry uses Opening Balance
    Equity (3300).

    `balances` is `[{account_id, amount}, ...]`. amount is the desired new
    balance interpreted on the account's natural side: a debit-normal asset
    with `amount=1000` posts a debit of 1000 to that account.

    If any rows already exist on any of the named accounts, refuse unless
    `force=True`.
    """
    if not balances:
        raise AccountingFoundationsError("balances cannot be empty")

    obe = (
        await db.execute(select(Account).where(Account.code == "3300"))
    ).scalar_one_or_none()
    if obe is None:
        raise AccountingFoundationsError("Opening Balance Equity (3300) is missing from COA")

    account_ids = [b["account_id"] for b in balances]
    accounts = (
        await db.execute(select(Account).where(Account.id.in_(account_ids)))
    ).scalars().all()
    by_id = {a.id: a for a in accounts}
    missing = [str(aid) for aid in account_ids if aid not in by_id]
    if missing:
        raise AccountingFoundationsError(f"Accounts not found: {', '.join(missing)}")

    # Activity guard
    if not force:
        existing = (
            await db.execute(
                select(JournalLine.id).where(JournalLine.account_id.in_(account_ids)).limit(1)
            )
        ).first()
        if existing:
            raise AccountingFoundationsError(
                "Some accounts already have activity; pass force=true to override"
            )

    je_lines: list[JournalLineCreate] = []
    obe_signed = Decimal("0")
    for b in balances:
        a = by_id[b["account_id"]]
        amt = Decimal(str(b["amount"]))
        if amt == 0:
            continue
        if a.normal_balance == "debit":
            # Dr the asset → Cr OBE
            entry_type = "debit"
            obe_signed += amt
        else:
            # Cr the liability/equity → Dr OBE
            entry_type = "credit"
            obe_signed -= amt
        je_lines.append(
            JournalLineCreate(
                account_id=a.id,
                entry_type=entry_type,
                amount=abs(amt),
                description=f"Opening balance for {a.code} {a.name}",
            )
        )

    if not je_lines:
        raise AccountingFoundationsError("All requested balances were zero — nothing to post")

    # Balance against OBE
    if obe_signed != 0:
        je_lines.append(
            JournalLineCreate(
                account_id=obe.id,
                entry_type="credit" if obe_signed > 0 else "debit",
                amount=abs(obe_signed),
                description="Opening balance equity offset",
            )
        )

    try:
        return await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=as_of,
                source_type="starting_balances",
                memo="Migration: opening balances",
                lines=je_lines,
            ),
        )
    except AccountingValidationError as e:
        raise AccountingFoundationsError(str(e)) from e
