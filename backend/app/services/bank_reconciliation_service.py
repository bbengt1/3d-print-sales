"""Bank reconciliation lifecycle service (#239).

Lifecycle:
- start: caller provides account_id + statement_end_date + statement_ending_balance.
  We snapshot opening_balance = sum of cleared+reconciled lines on this account
  posted before today's effective recon. Status='in_progress'.
- toggle_line: include/exclude a specific journal line in the recon. Including
  flips the journal line's cleared_status to 'cleared'; excluding flips it back
  to 'uncleared' (only safe while the recon is in_progress).
- finalize: refuses unless `book_balance == statement_ending_balance`. On
  success flips status='finalized', flips every included line's
  cleared_status='reconciled', stamps finalized_at + finalized_by_user_id.
- reopen: admin-only, flips status back to 'in_progress' and every line back
  to 'cleared' (still kept on the recon, ready for re-finalize).

Hard-block on edits: any attempt to update or delete a journal line whose
cleared_status='reconciled' is rejected by the service-level guard
`assert_journal_line_editable`. Endpoints that mutate journal lines should
call this guard before saving.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.bank_reconciliation import BankReconciliation, BankReconciliationLine
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine


class BankReconciliationError(RuntimeError):
    """Operational error during reconciliation lifecycle."""


class JournalLineLockedError(BankReconciliationError):
    """Raised when caller tries to edit a journal line whose cleared_status is reconciled."""


CLEARED_STATUS_RECONCILED = "reconciled"
CLEARED_STATUS_CLEARED = "cleared"
CLEARED_STATUS_UNCLEARED = "uncleared"

STATUS_IN_PROGRESS = "in_progress"
STATUS_FINALIZED = "finalized"


async def _ensure_bank_account(db: AsyncSession, account_id: uuid.UUID) -> Account:
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if account is None:
        raise BankReconciliationError(f"Account {account_id} not found")
    if not account.is_bank_account:
        raise BankReconciliationError(
            f"Account {account.code} is not flagged is_bank_account=True"
        )
    return account


def _signed_amount(line: JournalLine, account: Account) -> Decimal:
    """Return the signed amount this journal line contributes to the account
    balance. Debit-normal accounts: debit positive, credit negative; vice
    versa for credit-normal. (Bank account assets are debit-normal.)
    """
    sign = 1 if account.normal_balance == "debit" else -1
    if line.entry_type == "debit":
        return Decimal(line.amount) * sign
    return Decimal(line.amount) * (-sign)


async def compute_account_balance(
    db: AsyncSession,
    account_id: uuid.UUID,
    *,
    only_cleared: bool = False,
    through_date: date | None = None,
) -> Decimal:
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if account is None:
        raise BankReconciliationError(f"Account {account_id} not found")

    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalLine.account_id == account_id)
    )
    rows = (await db.execute(stmt)).all()

    total = Decimal("0")
    for line, entry in rows:
        if through_date is not None and entry.entry_date > through_date:
            continue
        if only_cleared and line.cleared_status not in (CLEARED_STATUS_CLEARED, CLEARED_STATUS_RECONCILED):
            continue
        total += _signed_amount(line, account)
    return total


async def start_reconciliation(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    statement_end_date: date,
    statement_ending_balance: Decimal,
    notes: str | None = None,
) -> BankReconciliation:
    await _ensure_bank_account(db, account_id)

    opening = await compute_account_balance(
        db, account_id, only_cleared=True, through_date=statement_end_date
    )

    recon = BankReconciliation(
        account_id=account_id,
        statement_end_date=statement_end_date,
        statement_ending_balance=Decimal(statement_ending_balance),
        opening_balance=opening,
        status=STATUS_IN_PROGRESS,
        notes=notes,
    )
    db.add(recon)
    await db.flush()
    return recon


async def list_eligible_lines(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    statement_end_date: date,
) -> list[tuple[JournalLine, JournalEntry]]:
    """Return (line, entry) pairs for lines posting to this account on or
    before statement_end_date and not yet reconciled.
    """
    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(
            JournalLine.account_id == account_id,
            JournalLine.cleared_status != CLEARED_STATUS_RECONCILED,
            JournalEntry.entry_date <= statement_end_date,
        )
        .order_by(JournalEntry.entry_date, JournalLine.line_number)
    )
    return list((await db.execute(stmt)).all())


async def include_line(
    db: AsyncSession,
    *,
    reconciliation_id: uuid.UUID,
    journal_line_id: uuid.UUID,
) -> BankReconciliationLine:
    recon = await _get_in_progress_recon(db, reconciliation_id)

    line_row = (
        await db.execute(
            select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalLine.id == journal_line_id)
        )
    ).first()
    if line_row is None:
        raise BankReconciliationError(f"Journal line {journal_line_id} not found")
    line, entry = line_row
    if line.account_id != recon.account_id:
        raise BankReconciliationError("Journal line account does not match reconciliation account")
    if line.cleared_status == CLEARED_STATUS_RECONCILED:
        raise BankReconciliationError("Journal line is already reconciled in another recon")
    # #271 P1: enforce statement-end-date bound — `/toggle-line` accepts an
    # arbitrary journal_line_id, so without this guard a client could fold a
    # future-dated transaction into an older statement reconciliation and
    # still finalize if totals happened to balance. Mirror the predicate
    # used in `list_eligible_lines`.
    if entry.entry_date > recon.statement_end_date:
        raise BankReconciliationError(
            f"Journal line entry date {entry.entry_date} is after statement end date "
            f"{recon.statement_end_date}; cannot include in this reconciliation"
        )

    existing = (
        await db.execute(
            select(BankReconciliationLine).where(
                BankReconciliationLine.reconciliation_id == reconciliation_id,
                BankReconciliationLine.journal_line_id == journal_line_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    # #271 P1: cross-reconciliation guard — a journal line must not be linked
    # to more than one active (non-finalized) reconciliation at a time, or
    # overlapping drafts/reopens would double-count the same transaction and
    # could leave one line represented in multiple finalized reconciliations.
    other_active = (
        await db.execute(
            select(BankReconciliationLine.reconciliation_id)
            .join(
                BankReconciliation,
                BankReconciliation.id == BankReconciliationLine.reconciliation_id,
            )
            .where(
                BankReconciliationLine.journal_line_id == journal_line_id,
                BankReconciliationLine.reconciliation_id != reconciliation_id,
                BankReconciliation.status == STATUS_IN_PROGRESS,
            )
        )
    ).first()
    if other_active is not None:
        raise BankReconciliationError(
            f"Journal line {journal_line_id} is already linked to another "
            f"active reconciliation ({other_active[0]})"
        )

    rline = BankReconciliationLine(
        reconciliation_id=reconciliation_id,
        journal_line_id=journal_line_id,
        amount=Decimal(line.amount),
    )
    db.add(rline)
    line.cleared_status = CLEARED_STATUS_CLEARED
    await db.flush()
    return rline


async def exclude_line(
    db: AsyncSession,
    *,
    reconciliation_id: uuid.UUID,
    journal_line_id: uuid.UUID,
) -> None:
    recon = await _get_in_progress_recon(db, reconciliation_id)

    rline = (
        await db.execute(
            select(BankReconciliationLine).where(
                BankReconciliationLine.reconciliation_id == reconciliation_id,
                BankReconciliationLine.journal_line_id == journal_line_id,
            )
        )
    ).scalar_one_or_none()
    if rline is None:
        return

    line = (await db.execute(select(JournalLine).where(JournalLine.id == journal_line_id))).scalar_one_or_none()
    await db.delete(rline)
    if line is not None and line.cleared_status == CLEARED_STATUS_CLEARED:
        # Only flip back to uncleared if no other in_progress recon includes
        # this line.
        other = (
            await db.execute(
                select(BankReconciliationLine).where(
                    BankReconciliationLine.journal_line_id == journal_line_id,
                    BankReconciliationLine.reconciliation_id != reconciliation_id,
                )
            )
        ).first()
        if other is None:
            line.cleared_status = CLEARED_STATUS_UNCLEARED
    _ = recon
    await db.flush()


async def compute_book_balance(
    db: AsyncSession,
    reconciliation_id: uuid.UUID,
) -> Decimal:
    """Returns: sum of signed amounts across this recon's included lines plus
    the recon's opening_balance."""
    recon = (
        await db.execute(
            select(BankReconciliation).where(BankReconciliation.id == reconciliation_id)
        )
    ).scalar_one_or_none()
    if recon is None:
        raise BankReconciliationError("Reconciliation not found")

    account = (await db.execute(select(Account).where(Account.id == recon.account_id))).scalar_one()

    rows = (
        await db.execute(
            select(JournalLine, BankReconciliationLine)
            .join(BankReconciliationLine, BankReconciliationLine.journal_line_id == JournalLine.id)
            .where(BankReconciliationLine.reconciliation_id == reconciliation_id)
        )
    ).all()

    total = Decimal(recon.opening_balance)
    for line, _rline in rows:
        total += _signed_amount(line, account)
    return total


async def finalize_reconciliation(
    db: AsyncSession,
    *,
    reconciliation_id: uuid.UUID,
    finalized_by_user_id: uuid.UUID | None,
) -> BankReconciliation:
    recon = await _get_in_progress_recon(db, reconciliation_id)

    # #314 P2: refuse finalize if statement_end_date is on/before the closed
    # period — finalizing flips lines to `reconciled` which then become
    # uneditable, and that would silently extend a closed-period lock.
    from app.services.accounting_service import get_period_close_date

    close_date = await get_period_close_date(db)
    if close_date and recon.statement_end_date <= close_date:
        raise BankReconciliationError(
            f"Cannot finalize: statement end date {recon.statement_end_date} is on or "
            f"before the closed-period date {close_date}. Reopen books to finalize."
        )

    book = await compute_book_balance(db, reconciliation_id)
    if book != Decimal(recon.statement_ending_balance):
        raise BankReconciliationError(
            f"Cannot finalize: book balance {book} != statement balance {recon.statement_ending_balance}"
        )

    rows = (
        await db.execute(
            select(JournalLine)
            .join(BankReconciliationLine, BankReconciliationLine.journal_line_id == JournalLine.id)
            .where(BankReconciliationLine.reconciliation_id == reconciliation_id)
        )
    ).scalars().all()
    for line in rows:
        line.cleared_status = CLEARED_STATUS_RECONCILED

    recon.status = STATUS_FINALIZED
    recon.finalized_at = datetime.now(timezone.utc)
    recon.finalized_by_user_id = finalized_by_user_id
    await db.flush()
    return recon


async def reopen_reconciliation(
    db: AsyncSession,
    *,
    reconciliation_id: uuid.UUID,
) -> BankReconciliation:
    recon = (
        await db.execute(
            select(BankReconciliation).where(BankReconciliation.id == reconciliation_id)
        )
    ).scalar_one_or_none()
    if recon is None:
        raise BankReconciliationError("Reconciliation not found")
    if recon.status != STATUS_FINALIZED:
        raise BankReconciliationError("Only finalized reconciliations can be reopened")

    rows = (
        await db.execute(
            select(JournalLine)
            .join(BankReconciliationLine, BankReconciliationLine.journal_line_id == JournalLine.id)
            .where(BankReconciliationLine.reconciliation_id == reconciliation_id)
        )
    ).scalars().all()
    for line in rows:
        if line.cleared_status == CLEARED_STATUS_RECONCILED:
            line.cleared_status = CLEARED_STATUS_CLEARED

    recon.status = STATUS_IN_PROGRESS
    recon.finalized_at = None
    recon.finalized_by_user_id = None
    await db.flush()
    return recon


async def _get_in_progress_recon(
    db: AsyncSession, reconciliation_id: uuid.UUID
) -> BankReconciliation:
    recon = (
        await db.execute(
            select(BankReconciliation).where(BankReconciliation.id == reconciliation_id)
        )
    ).scalar_one_or_none()
    if recon is None:
        raise BankReconciliationError("Reconciliation not found")
    if recon.status != STATUS_IN_PROGRESS:
        raise BankReconciliationError(
            f"Reconciliation {reconciliation_id} is {recon.status}, not in_progress"
        )
    return recon


async def assert_journal_line_editable(
    db: AsyncSession, journal_line_id: uuid.UUID
) -> None:
    """Hard-block edits/deletes on reconciled journal lines.

    Endpoints that mutate journal lines (or upstream entities that fold into a
    journal line edit) should call this **before** writing to ensure they
    don't silently corrupt a finalized reconciliation. Raises
    `JournalLineLockedError` (subclass of BankReconciliationError) which
    callers should turn into a 409 to the API client.
    """
    line = (await db.execute(select(JournalLine).where(JournalLine.id == journal_line_id))).scalar_one_or_none()
    if line is None:
        return
    if line.cleared_status == CLEARED_STATUS_RECONCILED:
        raise JournalLineLockedError(
            f"Journal line {journal_line_id} is reconciled and cannot be edited; "
            f"reopen the relevant bank reconciliation first."
        )
