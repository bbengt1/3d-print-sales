"""Expense claim lifecycle (#251).

Lifecycle: draft → submitted → approved → reimbursed → cancelled.
Approve posts JE: Dr expense lines, Cr Owner Reimbursable Liability.
Reimburse posts JE: Dr Owner Reimbursable Liability, Cr cash.
Cancel after approve reverses the approve JE.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.expense_claim import ExpenseClaim, ExpenseClaimLine
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
    reverse_journal_entry,
)
from app.services.reference_number_service import next_number


class ExpenseClaimError(RuntimeError):
    pass


STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_REIMBURSED = "reimbursed"
STATUS_CANCELLED = "cancelled"


async def _liability_account(db: AsyncSession) -> Account:
    a = (await db.execute(select(Account).where(Account.code == "2300"))).scalar_one_or_none()
    if a is None:
        raise ExpenseClaimError("Owner Reimbursable Liability account (2300) is missing from COA")
    return a


async def _ap_account(db: AsyncSession) -> Account:
    a = (await db.execute(select(Account).where(Account.code == "2000"))).scalar_one_or_none()
    if a is None:
        raise ExpenseClaimError("Accounts Payable account (2000) is missing from COA")
    return a


async def _mileage_rate(db: AsyncSession) -> Decimal | None:
    """#324 P2: read configured mileage rate (e.g. 0.67 for $/mile)."""
    from app.models.setting import Setting

    row = (
        await db.execute(
            select(Setting).where(Setting.key == "expense_claims.mileage_rate_per_mile")
        )
    ).scalar_one_or_none()
    if row is None or not row.value:
        return None
    try:
        return Decimal(row.value.strip())
    except Exception:
        return None


async def create_claim(
    db: AsyncSession,
    *,
    payer_kind: str = "owner",
    payer_name: str,
    notes: str | None = None,
    lines: list[dict],
) -> ExpenseClaim:
    if not lines:
        raise ExpenseClaimError("Claim must have at least one line")
    number = await next_number(db, "expense_claim")
    total = Decimal("0")
    claim = ExpenseClaim(
        claim_number=number,
        payer_kind=payer_kind,
        payer_name=payer_name,
        notes=notes,
        status=STATUS_DRAFT,
    )
    db.add(claim)
    await db.flush()
    # #324 P2: lookup the configured mileage rate once for any mileage lines.
    rate = await _mileage_rate(db)
    for line in lines:
        kind = line.get("line_kind", "expense")
        miles_raw = line.get("miles")
        if kind == "mileage":
            if miles_raw is None or Decimal(str(miles_raw)) <= 0:
                raise ExpenseClaimError("Mileage line requires miles > 0")
            if rate is None:
                raise ExpenseClaimError(
                    "Configure setting `expense_claims.mileage_rate_per_mile` before adding mileage lines"
                )
            miles_dec = Decimal(str(miles_raw))
            amt = (miles_dec * rate).quantize(Decimal("0.01"))
            mileage_rate_used = rate
        else:
            amt = Decimal(str(line["amount"]))
            miles_dec = None
            mileage_rate_used = None
        if amt <= 0:
            raise ExpenseClaimError("Line amount must be > 0")
        total += amt
        db.add(
            ExpenseClaimLine(
                claim_id=claim.id,
                description=line["description"],
                expense_account_id=line["expense_account_id"],
                amount=amt,
                line_kind=kind,
                miles=miles_dec,
                mileage_rate_used=mileage_rate_used,
                notes=line.get("notes"),
            )
        )
    claim.total_amount = total.quantize(Decimal("0.01"))
    await db.flush()
    return claim


async def submit_claim(db: AsyncSession, claim_id: uuid.UUID) -> ExpenseClaim:
    claim = await _require(db, claim_id)
    if claim.status != STATUS_DRAFT:
        raise ExpenseClaimError(f"Cannot submit claim in status {claim.status}")
    claim.status = STATUS_SUBMITTED
    claim.submitted_on = datetime.now(timezone.utc).date()
    await db.flush()
    return claim


async def approve_claim(db: AsyncSession, claim_id: uuid.UUID, *, approve_date: date | None = None) -> ExpenseClaim:
    claim = await _require(db, claim_id)
    if claim.status not in (STATUS_DRAFT, STATUS_SUBMITTED):
        raise ExpenseClaimError(f"Cannot approve claim in status {claim.status}")

    liability = await _liability_account(db)
    lines = (
        await db.execute(select(ExpenseClaimLine).where(ExpenseClaimLine.claim_id == claim.id))
    ).scalars().all()

    je_lines: list[JournalLineCreate] = []
    for line in lines:
        je_lines.append(
            JournalLineCreate(
                account_id=line.expense_account_id,
                entry_type="debit",
                amount=Decimal(line.amount),
                description=f"Expense claim {claim.claim_number}: {line.description}",
            )
        )
    je_lines.append(
        JournalLineCreate(
            account_id=liability.id,
            entry_type="credit",
            amount=Decimal(claim.total_amount),
            description=f"Expense claim {claim.claim_number} payable to {claim.payer_name}",
        )
    )

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=approve_date or datetime.now(timezone.utc).date(),
                source_type="expense_claim_approval",
                source_id=str(claim.id),
                memo=f"Approve expense claim {claim.claim_number}",
                lines=je_lines,
            ),
        )
    except AccountingValidationError as e:
        raise ExpenseClaimError(str(e)) from e

    claim.status = STATUS_APPROVED
    claim.journal_entry_id = entry.id
    await db.flush()
    return claim


async def reimburse_claim(
    db: AsyncSession,
    claim_id: uuid.UUID,
    *,
    cash_account_id: uuid.UUID,
    paid_on: date | None = None,
) -> ExpenseClaim:
    claim = await _require(db, claim_id)
    if claim.status != STATUS_APPROVED:
        raise ExpenseClaimError(f"Cannot reimburse claim in status {claim.status}")

    liability = await _liability_account(db)
    cash = (await db.execute(select(Account).where(Account.id == cash_account_id))).scalar_one_or_none()
    if cash is None:
        raise ExpenseClaimError("Cash account not found")

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=paid_on or datetime.now(timezone.utc).date(),
                source_type="expense_claim_reimbursement",
                source_id=str(claim.id),
                memo=f"Reimburse expense claim {claim.claim_number} to {claim.payer_name}",
                lines=[
                    JournalLineCreate(
                        account_id=liability.id,
                        entry_type="debit",
                        amount=Decimal(claim.total_amount),
                        description=f"Reimbursement {claim.claim_number}",
                    ),
                    JournalLineCreate(
                        account_id=cash.id,
                        entry_type="credit",
                        amount=Decimal(claim.total_amount),
                        description=f"Reimbursement {claim.claim_number}",
                    ),
                ],
            ),
        )
    except AccountingValidationError as e:
        raise ExpenseClaimError(str(e)) from e

    claim.status = STATUS_REIMBURSED
    claim.reimbursement_journal_entry_id = entry.id
    await db.flush()
    return claim


async def reimburse_claim_as_bill(
    db: AsyncSession,
    claim_id: uuid.UUID,
    *,
    vendor_id: uuid.UUID,
    due_date: date | None = None,
    description: str | None = None,
) -> ExpenseClaim:
    """#324 P2 alternative reimbursement path: convert the owner-reimbursable
    balance into an Accounts Payable balance owed to a vendor.

    Posts JE: Dr Owner Reimbursable Liability (2300), Cr Accounts Payable
    (2000) at claim total, then creates a tracking `Bill` row pointing at
    the chosen vendor. The bill is then paid through the normal AP bill
    payment flow.

    The bill is created directly in this service rather than through the
    `/accounting/bills` endpoint so the linked account can be the
    Owner Reimbursable Liability (the API path requires an expense
    account, which doesn't fit this conversion).
    """
    from app.models.bill import Bill
    from app.models.vendor import Vendor

    claim = await _require(db, claim_id)
    if claim.status != STATUS_APPROVED:
        raise ExpenseClaimError(f"Cannot reimburse claim in status {claim.status}")
    if claim.bill_id is not None:
        raise ExpenseClaimError("Claim already linked to a reimbursement bill")

    vendor = (
        await db.execute(select(Vendor).where(Vendor.id == vendor_id))
    ).scalar_one_or_none()
    if vendor is None:
        raise ExpenseClaimError("Vendor not found")

    liability = await _liability_account(db)
    ap = await _ap_account(db)
    today = datetime.now(timezone.utc).date()

    try:
        entry = await create_journal_entry(
            db,
            JournalEntryCreate(
                entry_date=today,
                source_type="expense_claim_reimbursement_bill",
                source_id=str(claim.id),
                memo=(
                    f"Reimburse expense claim {claim.claim_number} via bill to "
                    f"{vendor.name}"
                ),
                lines=[
                    JournalLineCreate(
                        account_id=liability.id,
                        entry_type="debit",
                        amount=Decimal(claim.total_amount),
                        description=f"Reimbursement {claim.claim_number}",
                    ),
                    JournalLineCreate(
                        account_id=ap.id,
                        entry_type="credit",
                        amount=Decimal(claim.total_amount),
                        description=f"Reimbursement {claim.claim_number} -> AP {vendor.name}",
                    ),
                ],
            ),
        )
    except AccountingValidationError as e:
        raise ExpenseClaimError(str(e)) from e

    bill = Bill(
        vendor_id=vendor.id,
        # Account_id points at the Owner Reimbursable Liability so that any
        # subsequent /bills/{id}/payments call here lands the cash credit
        # against the same account the JE balanced from. (The API-layer
        # validator that requires an expense account is bypassed by writing
        # the row directly through the ORM.)
        account_id=liability.id,
        description=description or f"Reimburse expense claim {claim.claim_number}",
        issue_date=today,
        due_date=due_date,
        amount=Decimal(claim.total_amount),
        status="open",
    )
    db.add(bill)
    await db.flush()

    claim.status = STATUS_REIMBURSED
    claim.reimbursement_journal_entry_id = entry.id
    claim.bill_id = bill.id
    await db.flush()
    return claim


async def submit_claim_for_approval(
    db: AsyncSession,
    claim_id: uuid.UUID,
    *,
    requested_by_user_id: uuid.UUID,
):
    """#324 P2 approval-workflow integration.

    When the `expense_claims.require_approval_to_approve` setting is truthy
    (or when this function is called directly), create an
    ``ApprovalRequest`` of type ``expense_claim_approval`` so an admin
    has to approve the claim through the central approvals queue before
    `approve_claim` can run. The claim moves to ``submitted`` either way
    so it's locked from editing.
    """
    from app.models.approval_request import ApprovalRequest

    claim = await _require(db, claim_id)
    if claim.status not in (STATUS_DRAFT, STATUS_SUBMITTED):
        raise ExpenseClaimError(
            f"Cannot request approval for claim in status {claim.status}"
        )

    request = ApprovalRequest(
        action_type="expense_claim_approval",
        entity_type="expense_claim",
        entity_id=str(claim.id),
        requested_by_user_id=requested_by_user_id,
        status="pending",
        reason=f"Approve expense claim {claim.claim_number} for {claim.payer_name}",
        request_payload={"claim_id": str(claim.id)},
    )
    db.add(request)
    if claim.status == STATUS_DRAFT:
        claim.status = STATUS_SUBMITTED
        claim.submitted_on = datetime.now(timezone.utc).date()
    await db.flush()
    return request


async def is_approval_required_to_approve(db: AsyncSession) -> bool:
    """Read the toggle setting; truthy values: 'true', '1', 'yes' (case-insensitive)."""
    from app.models.setting import Setting

    row = (
        await db.execute(
            select(Setting).where(Setting.key == "expense_claims.require_approval_to_approve")
        )
    ).scalar_one_or_none()
    return bool(row and (row.value or "").strip().lower() in ("true", "1", "yes"))


async def cancel_claim(db: AsyncSession, claim_id: uuid.UUID) -> ExpenseClaim:
    claim = await _require(db, claim_id)
    if claim.status == STATUS_CANCELLED:
        return claim
    if claim.status == STATUS_REIMBURSED:
        raise ExpenseClaimError("Cannot cancel a reimbursed claim; reverse the reimbursement first")

    # Reverse the approve JE if posted
    if claim.status == STATUS_APPROVED and claim.journal_entry_id is not None:
        from app.schemas.accounting import JournalEntryReverse

        try:
            await reverse_journal_entry(
                db,
                entry_id=claim.journal_entry_id,
                payload=JournalEntryReverse(
                    reversal_date=datetime.now(timezone.utc).date(),
                    memo=f"Reverse approval — cancelled expense claim {claim.claim_number}",
                ),
            )
        except AccountingValidationError as e:
            raise ExpenseClaimError(str(e)) from e

    claim.status = STATUS_CANCELLED
    await db.flush()
    return claim


async def _require(db: AsyncSession, claim_id: uuid.UUID) -> ExpenseClaim:
    claim = (await db.execute(select(ExpenseClaim).where(ExpenseClaim.id == claim_id))).scalar_one_or_none()
    if claim is None:
        raise ExpenseClaimError("Expense claim not found")
    return claim
