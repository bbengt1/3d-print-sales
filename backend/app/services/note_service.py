"""Credit + debit note lifecycle (#248).

Phase 1:
- Create draft with line items
- Issue: posts JE
  - Credit note: Cr AR (1100) / Dr Sales Returns + line accounts
  - Debit note: Cr Purchase Returns + line accounts / Dr AP (2000)
- Apply to invoice/bill: posts JE that reduces both sides
  - Credit note application: Dr Sales Returns / Cr AR (against the invoice)
  - Debit note application: Dr AP (against the bill) / Cr Purchase Returns
- Void: blocked once any application has been recorded.

Restock interaction with #242 finished-goods layers, refund-in-cash,
email scope registration, marketplace bridging are all deferred to
Phase 2.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.bill import Bill
from app.models.credit_note import CreditNote, CreditNoteApplication, CreditNoteLine
from app.models.debit_note import DebitNote, DebitNoteApplication, DebitNoteLine
from app.models.invoice import Invoice
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
)
from app.services.reference_number_service import next_number


class NoteError(RuntimeError):
    pass


async def _account_by_code(db: AsyncSession, code: str) -> Account:
    a = (await db.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
    if a is None:
        raise NoteError(f"COA missing account code {code}; run migration")
    return a


# ---------- credit notes ----------


async def create_credit_note(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    issued_on: date,
    lines: list[dict],
    original_invoice_id: uuid.UUID | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> CreditNote:
    if not lines:
        raise NoteError("Credit note must have at least one line")
    number = await next_number(db, "credit_note")
    note = CreditNote(
        credit_note_number=number,
        customer_id=customer_id,
        original_invoice_id=original_invoice_id,
        issued_on=issued_on,
        status="draft",
        reason=reason,
        notes=notes,
    )
    db.add(note)
    await db.flush()
    subtotal = Decimal("0")
    for line in lines:
        qty = Decimal(str(line["quantity"]))
        price = Decimal(str(line["unit_price"]))
        total = (qty * price).quantize(Decimal("0.01"))
        subtotal += total
        db.add(
            CreditNoteLine(
                credit_note_id=note.id,
                description=line["description"],
                quantity=qty,
                unit_price=price,
                line_total=total,
                account_id=line["account_id"],
            )
        )
    note.subtotal_amount = subtotal
    note.total_amount = subtotal  # tax flow deferred to Phase 2
    await db.flush()
    return note


async def issue_credit_note(db: AsyncSession, note_id: uuid.UUID) -> CreditNote:
    note = await _require_credit_note(db, note_id)
    if note.status != "draft":
        raise NoteError(f"Cannot issue credit note in status {note.status}")

    ar = await _account_by_code(db, "1100")
    sales_returns = await _account_by_code(db, "4800")
    lines = (
        await db.execute(select(CreditNoteLine).where(CreditNoteLine.credit_note_id == note.id))
    ).scalars().all()

    # JE: Cr AR (total) / Dr each line's account at line_total
    je_lines = [
        JournalLineCreate(
            account_id=ar.id,
            entry_type="credit",
            amount=Decimal(note.total_amount),
            description=f"Credit note {note.credit_note_number}",
        )
    ]
    for line in lines:
        # If the line points at a revenue account (the typical "reverse a
        # sale" case), debiting that account is the right reversal. If the
        # operator picked Sales Returns (4800), we still debit it.
        je_lines.append(
            JournalLineCreate(
                account_id=line.account_id,
                entry_type="debit",
                amount=Decimal(line.line_total),
                description=f"Credit note line: {line.description}",
            )
        )
    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=note.issued_on,
                source_type="credit_note",
                source_id=str(note.id),
                memo=f"Issue credit note {note.credit_note_number}",
                lines=je_lines,
            ),
        )
    except AccountingValidationError as e:
        raise NoteError(str(e)) from e

    note.status = "issued"
    note.journal_entry_id = entry.id
    await db.flush()
    _ = sales_returns  # 4800 reserved for Phase 2 refund-in-cash flow
    return note


async def apply_credit_note(
    db: AsyncSession,
    *,
    note_id: uuid.UUID,
    invoice_id: uuid.UUID,
    amount: Decimal,
    applied_on: date | None = None,
) -> CreditNoteApplication:
    note = await _require_credit_note(db, note_id)
    if note.status not in ("issued", "partially_applied"):
        raise NoteError(f"Cannot apply credit note in status {note.status}")
    amt = Decimal(amount)
    if amt <= 0:
        raise NoteError("amount must be > 0")
    remaining = Decimal(note.total_amount) - Decimal(note.applied_amount)
    if amt > remaining:
        raise NoteError(f"amount exceeds remaining credit ({remaining})")

    invoice = (await db.execute(select(Invoice).where(Invoice.id == invoice_id))).scalar_one_or_none()
    if invoice is None:
        raise NoteError("Invoice not found")
    if invoice.customer_id and invoice.customer_id != note.customer_id:
        raise NoteError("Invoice belongs to a different customer")

    ar = await _account_by_code(db, "1100")
    sales_returns = await _account_by_code(db, "4800")

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=applied_on or datetime.now(timezone.utc).date(),
                source_type="credit_note_application",
                source_id=str(note.id),
                memo=f"Apply credit note {note.credit_note_number} to invoice {invoice.invoice_number}",
                lines=[
                    # Reduce the invoice's AR side by re-posting a credit
                    JournalLineCreate(
                        account_id=ar.id,
                        entry_type="credit",
                        amount=amt,
                        description=f"Apply credit note to invoice {invoice.invoice_number}",
                    ),
                    JournalLineCreate(
                        account_id=sales_returns.id,
                        entry_type="debit",
                        amount=amt,
                        description=f"Apply credit note {note.credit_note_number}",
                    ),
                ],
            ),
        )
    except AccountingValidationError as e:
        raise NoteError(str(e)) from e

    application = CreditNoteApplication(
        credit_note_id=note.id,
        invoice_id=invoice.id,
        amount=amt,
        applied_on=applied_on or datetime.now(timezone.utc).date(),
        journal_entry_id=entry.id,
    )
    db.add(application)
    note.applied_amount = Decimal(note.applied_amount) + amt
    if note.applied_amount >= note.total_amount:
        note.status = "applied"
    else:
        note.status = "partially_applied"

    # Reduce the invoice's outstanding by treating the application as credits_applied
    invoice.credits_applied = Decimal(invoice.credits_applied) + amt
    invoice.balance_due = max(Decimal("0"), Decimal(invoice.balance_due) - amt)
    await db.flush()
    return application


async def void_credit_note(db: AsyncSession, note_id: uuid.UUID) -> CreditNote:
    note = await _require_credit_note(db, note_id)
    if note.status == "void":
        return note
    if Decimal(note.applied_amount) > 0:
        raise NoteError("Cannot void a credit note that has been applied; reverse the applications first")
    if note.status == "issued":
        # Reverse the issue JE
        from app.schemas.accounting import JournalEntryReverse
        from app.services.accounting_service import reverse_journal_entry

        if note.journal_entry_id is not None:
            try:
                await reverse_journal_entry(
                    db,
                    entry_id=note.journal_entry_id,
                    payload=JournalEntryReverse(
                        reversal_date=datetime.now(timezone.utc).date(),
                        memo=f"Void credit note {note.credit_note_number}",
                    ),
                )
            except AccountingValidationError as e:
                raise NoteError(str(e)) from e
    note.status = "void"
    await db.flush()
    return note


async def _require_credit_note(db: AsyncSession, note_id: uuid.UUID) -> CreditNote:
    note = (await db.execute(select(CreditNote).where(CreditNote.id == note_id))).scalar_one_or_none()
    if note is None:
        raise NoteError("Credit note not found")
    return note


# ---------- debit notes ----------


async def create_debit_note(
    db: AsyncSession,
    *,
    vendor_id: uuid.UUID,
    issued_on: date,
    lines: list[dict],
    original_bill_id: uuid.UUID | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> DebitNote:
    if not lines:
        raise NoteError("Debit note must have at least one line")
    number = await next_number(db, "debit_note")
    note = DebitNote(
        debit_note_number=number,
        vendor_id=vendor_id,
        original_bill_id=original_bill_id,
        issued_on=issued_on,
        status="draft",
        reason=reason,
        notes=notes,
    )
    db.add(note)
    await db.flush()
    subtotal = Decimal("0")
    for line in lines:
        qty = Decimal(str(line["quantity"]))
        price = Decimal(str(line["unit_price"]))
        total = (qty * price).quantize(Decimal("0.01"))
        subtotal += total
        db.add(
            DebitNoteLine(
                debit_note_id=note.id,
                description=line["description"],
                quantity=qty,
                unit_price=price,
                line_total=total,
                account_id=line["account_id"],
            )
        )
    note.subtotal_amount = subtotal
    note.total_amount = subtotal
    await db.flush()
    return note


async def issue_debit_note(db: AsyncSession, note_id: uuid.UUID) -> DebitNote:
    note = await _require_debit_note(db, note_id)
    if note.status != "draft":
        raise NoteError(f"Cannot issue debit note in status {note.status}")

    ap = await _account_by_code(db, "2000")
    purchase_returns = await _account_by_code(db, "5400")
    lines = (
        await db.execute(select(DebitNoteLine).where(DebitNoteLine.debit_note_id == note.id))
    ).scalars().all()

    # JE: Dr AP / Cr line account (or Cr Purchase Returns) for line_total
    je_lines = [
        JournalLineCreate(
            account_id=ap.id,
            entry_type="debit",
            amount=Decimal(note.total_amount),
            description=f"Debit note {note.debit_note_number}",
        )
    ]
    for line in lines:
        je_lines.append(
            JournalLineCreate(
                account_id=line.account_id,
                entry_type="credit",
                amount=Decimal(line.line_total),
                description=f"Debit note line: {line.description}",
            )
        )
    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=note.issued_on,
                source_type="debit_note",
                source_id=str(note.id),
                memo=f"Issue debit note {note.debit_note_number}",
                lines=je_lines,
            ),
        )
    except AccountingValidationError as e:
        raise NoteError(str(e)) from e

    note.status = "issued"
    note.journal_entry_id = entry.id
    await db.flush()
    _ = purchase_returns  # reserved for Phase 2 refund-from-vendor cash flow
    return note


async def apply_debit_note(
    db: AsyncSession,
    *,
    note_id: uuid.UUID,
    bill_id: uuid.UUID,
    amount: Decimal,
    applied_on: date | None = None,
) -> DebitNoteApplication:
    note = await _require_debit_note(db, note_id)
    if note.status not in ("issued", "partially_applied"):
        raise NoteError(f"Cannot apply debit note in status {note.status}")
    amt = Decimal(amount)
    if amt <= 0:
        raise NoteError("amount must be > 0")
    remaining = Decimal(note.total_amount) - Decimal(note.applied_amount)
    if amt > remaining:
        raise NoteError(f"amount exceeds remaining debit ({remaining})")

    bill = (await db.execute(select(Bill).where(Bill.id == bill_id))).scalar_one_or_none()
    if bill is None:
        raise NoteError("Bill not found")

    ap = await _account_by_code(db, "2000")
    purchase_returns = await _account_by_code(db, "5400")

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=applied_on or datetime.now(timezone.utc).date(),
                source_type="debit_note_application",
                source_id=str(note.id),
                memo=f"Apply debit note {note.debit_note_number} to bill",
                lines=[
                    JournalLineCreate(
                        account_id=ap.id,
                        entry_type="debit",
                        amount=amt,
                        description=f"Apply debit note to bill",
                    ),
                    JournalLineCreate(
                        account_id=purchase_returns.id,
                        entry_type="credit",
                        amount=amt,
                        description=f"Apply debit note {note.debit_note_number}",
                    ),
                ],
            ),
        )
    except AccountingValidationError as e:
        raise NoteError(str(e)) from e

    application = DebitNoteApplication(
        debit_note_id=note.id,
        bill_id=bill.id,
        amount=amt,
        applied_on=applied_on or datetime.now(timezone.utc).date(),
        journal_entry_id=entry.id,
    )
    db.add(application)
    note.applied_amount = Decimal(note.applied_amount) + amt
    if note.applied_amount >= note.total_amount:
        note.status = "applied"
    else:
        note.status = "partially_applied"
    await db.flush()
    return application


async def void_debit_note(db: AsyncSession, note_id: uuid.UUID) -> DebitNote:
    note = await _require_debit_note(db, note_id)
    if note.status == "void":
        return note
    if Decimal(note.applied_amount) > 0:
        raise NoteError("Cannot void an applied debit note; reverse the applications first")
    if note.status == "issued" and note.journal_entry_id is not None:
        from app.schemas.accounting import JournalEntryReverse
        from app.services.accounting_service import reverse_journal_entry

        try:
            await reverse_journal_entry(
                db,
                entry_id=note.journal_entry_id,
                payload=JournalEntryReverse(
                    reversal_date=datetime.now(timezone.utc).date(),
                    memo=f"Void debit note {note.debit_note_number}",
                ),
            )
        except AccountingValidationError as e:
            raise NoteError(str(e)) from e
    note.status = "void"
    await db.flush()
    return note


async def _require_debit_note(db: AsyncSession, note_id: uuid.UUID) -> DebitNote:
    note = (await db.execute(select(DebitNote).where(DebitNote.id == note_id))).scalar_one_or_none()
    if note is None:
        raise NoteError("Debit note not found")
    return note
