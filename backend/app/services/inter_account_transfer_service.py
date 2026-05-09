"""Inter-account transfer service (#246).

Always-posted: a single JE with two journal lines carrying independent
`posted_on` dates. Each leg reconciles against the appropriate statement
via the bank-recon flow from #239. No Phase-2 follow-up state machine.

Account pickers must satisfy `is_bank_account=True`. Same-currency only
in Phase 1 (multi-currency is Tier 3).

Edits and deletes are blocked when either leg is reconciled — uses the
edit-lock guard from #239.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.inter_account_transfer import InterAccountTransfer
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.services.bank_reconciliation_service import (
    JournalLineLockedError,
    assert_journal_line_editable,
)
from app.services.reference_number_service import next_number


class InterAccountTransferError(RuntimeError):
    pass


async def _ensure_bank_account(db: AsyncSession, account_id: uuid.UUID) -> Account:
    a = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if a is None:
        raise InterAccountTransferError(f"Account {account_id} not found")
    if not a.is_bank_account:
        raise InterAccountTransferError(f"Account {a.code} is not a bank account")
    return a


async def create_inter_account_transfer(
    db: AsyncSession,
    *,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
    amount: Decimal,
    paid_on: date,
    received_on: date | None = None,
    notes: str | None = None,
) -> InterAccountTransfer:
    if from_account_id == to_account_id:
        raise InterAccountTransferError("from_account and to_account must differ")
    amount = Decimal(amount)
    if amount <= 0:
        raise InterAccountTransferError("amount must be > 0")

    from_a = await _ensure_bank_account(db, from_account_id)
    await _ensure_bank_account(db, to_account_id)
    if received_on is None:
        received_on = paid_on

    # Build JE manually so we can set per-line posted_on. The accounting
    # service's create_journal_entry doesn't yet accept per-line dates;
    # we directly add JournalEntry + JournalLine here for this scope.
    number = await next_number(db, "inter_account_transfer")
    earlier = min(paid_on, received_on)

    # Allocate a unique JE number using the existing ad-hoc scheme.
    # (Long term, JE numbering should also flow through #243's allocator;
    # that's tracked in #260's accounting foundations cluster.)
    count = (await db.execute(select(JournalEntry))).scalars().all()
    je_number = f"JE-{earlier.year}-{len(count) + 1:04d}"

    je = JournalEntry(
        entry_number=je_number,
        entry_date=earlier,
        status="posted",
        source_type="inter_account_transfer",
        memo=f"Transfer {number}: {amount} from {from_a.code}",
        posted_at=datetime.now(timezone.utc),
    )
    db.add(je)
    await db.flush()

    # Per-account signed direction: from-side credits (decrease asset),
    # to-side debits (increase asset). Both are debit-normal accounts so
    # this is straightforward.
    db.add(
        JournalLine(
            journal_entry_id=je.id,
            account_id=from_account_id,
            line_number=1,
            entry_type="credit",
            amount=amount,
            description=f"Transfer {number} (out)",
            posted_on=paid_on,
        )
    )
    db.add(
        JournalLine(
            journal_entry_id=je.id,
            account_id=to_account_id,
            line_number=2,
            entry_type="debit",
            amount=amount,
            description=f"Transfer {number} (in)",
            posted_on=received_on,
        )
    )

    transfer = InterAccountTransfer(
        transfer_number=number,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        paid_on=paid_on,
        received_on=received_on,
        journal_entry_id=je.id,
        notes=notes,
    )
    db.add(transfer)
    await db.flush()
    return transfer


async def delete_inter_account_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> None:
    t = (await db.execute(select(InterAccountTransfer).where(InterAccountTransfer.id == transfer_id))).scalar_one_or_none()
    if t is None:
        raise InterAccountTransferError("Transfer not found")

    # Edit-lock guard: refuse if either leg is reconciled
    lines = (
        await db.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == t.journal_entry_id)
        )
    ).scalars().all()
    for line in lines:
        try:
            await assert_journal_line_editable(db, line.id)
        except JournalLineLockedError as e:
            raise InterAccountTransferError(str(e)) from e

    # Delete the JE + lines, then the transfer
    for line in lines:
        await db.delete(line)
    je = (
        await db.execute(select(JournalEntry).where(JournalEntry.id == t.journal_entry_id))
    ).scalar_one_or_none()
    if je is not None:
        await db.delete(je)
    await db.delete(t)
    await db.flush()
