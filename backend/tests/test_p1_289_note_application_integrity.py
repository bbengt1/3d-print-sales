"""Regression tests for PR #289 Codex P1 review (note_service application integrity).

Three issues addressed:
  1. apply_credit_note allowed applications larger than the invoice's current
     outstanding, leaving credits_applied past gross and tripping
     `_recalculate_invoice` later.
  2. apply_debit_note never verified vendor consistency between the debit note
     and the bill, so a debit note for vendor A could be applied to vendor B's
     bill.
  3. apply_debit_note never updated the bill's payable fields
     (amount_paid / status), so AP aging and payment-validation paths still
     allowed overpayment after the application.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.bill import Bill
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.vendor import Vendor
from app.services.note_service import (
    NoteError,
    apply_credit_note,
    apply_debit_note,
    create_credit_note,
    create_debit_note,
    issue_credit_note,
    issue_debit_note,
)


async def _accounts(db_session) -> dict[str, Account]:
    return {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}


async def _customer(db_session, name: str = "P1-289 Customer") -> Customer:
    c = Customer(name=name, email=f"{name.replace(' ', '').lower()}@x.test")
    db_session.add(c)
    await db_session.flush()
    return c


async def _vendor(db_session, name: str) -> Vendor:
    v = Vendor(name=name)
    db_session.add(v)
    await db_session.flush()
    return v


async def _invoice(
    db_session,
    customer_id,
    *,
    invoice_number: str,
    subtotal: Decimal,
    credits_applied: Decimal = Decimal("0"),
    amount_paid: Decimal = Decimal("0"),
) -> Invoice:
    total_due = subtotal - credits_applied
    inv = Invoice(
        invoice_number=invoice_number,
        customer_id=customer_id,
        issue_date=datetime.date(2026, 5, 1),
        subtotal=subtotal,
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=credits_applied,
        total_due=total_due,
        amount_paid=amount_paid,
        balance_due=total_due - amount_paid,
        status="sent",
    )
    db_session.add(inv)
    await db_session.flush()
    return inv


async def _bill(
    db_session,
    *,
    vendor_id,
    bill_number: str,
    amount: Decimal,
    accts: dict[str, Account],
) -> Bill:
    bill = Bill(
        bill_number=bill_number,
        vendor_id=vendor_id,
        account_id=accts["6500"].id,
        description=f"Bill {bill_number}",
        issue_date=datetime.date(2026, 5, 1),
        amount=amount,
        status="open",
    )
    db_session.add(bill)
    await db_session.flush()
    return bill


# ---------- (i) credit note larger than invoice balance ----------


@pytest.mark.asyncio
async def test_apply_credit_note_rejected_when_exceeds_invoice_outstanding(db_session):
    """A credit note larger than the invoice's outstanding balance must be rejected
    even when the note has plenty of remaining credit to spend."""
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    # Invoice has $50 outstanding (gross 100 - 50 already paid).
    inv = await _invoice(
        db_session,
        c.id,
        invoice_number="INV-P1-289-1",
        subtotal=Decimal("100"),
        amount_paid=Decimal("50"),
    )
    # Credit note is worth $200 (well-funded), but invoice can only absorb $50.
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[
            {
                "description": "Refund",
                "quantity": "1",
                "unit_price": "200",
                "account_id": accts["4800"].id,
            }
        ],
    )
    await issue_credit_note(db_session, n.id)

    with pytest.raises(NoteError, match="invoice outstanding"):
        await apply_credit_note(
            db_session, note_id=n.id, invoice_id=inv.id, amount=Decimal("75")
        )

    # Sanity: invoice state untouched.
    inv2 = (await db_session.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert Decimal(inv2.credits_applied) == Decimal("0")
    assert Decimal(inv2.amount_paid) == Decimal("50")

    # And applying within outstanding still works.
    app = await apply_credit_note(
        db_session, note_id=n.id, invoice_id=inv.id, amount=Decimal("50")
    )
    assert Decimal(app.amount) == Decimal("50")


# ---------- (ii) debit note vendor mismatch ----------


@pytest.mark.asyncio
async def test_apply_debit_note_rejected_when_vendor_mismatches_bill(db_session):
    """A debit note for vendor A must not be applicable to vendor B's bill."""
    accts = await _accounts(db_session)
    vendor_a = await _vendor(db_session, "Vendor A")
    vendor_b = await _vendor(db_session, "Vendor B")

    bill_b = await _bill(
        db_session,
        vendor_id=vendor_b.id,
        bill_number="BL-P1-289-B",
        amount=Decimal("100"),
        accts=accts,
    )

    note_a = await create_debit_note(
        db_session,
        vendor_id=vendor_a.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[
            {
                "description": "Return",
                "quantity": "1",
                "unit_price": "30",
                "account_id": accts["5400"].id,
            }
        ],
    )
    await issue_debit_note(db_session, note_a.id)

    with pytest.raises(NoteError, match="different vendor"):
        await apply_debit_note(
            db_session, note_id=note_a.id, bill_id=bill_b.id, amount=Decimal("30")
        )

    # Bill state untouched.
    refreshed = (await db_session.execute(select(Bill).where(Bill.id == bill_b.id))).scalar_one()
    assert Decimal(refreshed.amount_paid) == Decimal("0")
    assert refreshed.status == "open"


# ---------- (iii) bill payable updated by debit-note application ----------


@pytest.mark.asyncio
async def test_apply_debit_note_updates_bill_payable_fields(db_session):
    """A debit note application must reduce bill outstanding (amount_paid/status)
    so AP aging and payment-validation paths reflect operational reality."""
    accts = await _accounts(db_session)
    vendor = await _vendor(db_session, "Vendor C")
    bill = await _bill(
        db_session,
        vendor_id=vendor.id,
        bill_number="BL-P1-289-C",
        amount=Decimal("100"),
        accts=accts,
    )

    note = await create_debit_note(
        db_session,
        vendor_id=vendor.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[
            {
                "description": "Return",
                "quantity": "1",
                "unit_price": "100",
                "account_id": accts["5400"].id,
            }
        ],
    )
    await issue_debit_note(db_session, note.id)

    # Partial application: bill should become partially_paid with $40 absorbed.
    await apply_debit_note(
        db_session, note_id=note.id, bill_id=bill.id, amount=Decimal("40")
    )
    refreshed = (await db_session.execute(select(Bill).where(Bill.id == bill.id))).scalar_one()
    assert Decimal(refreshed.amount_paid) == Decimal("40")
    assert refreshed.status == "partially_paid"

    # Full remainder absorbed → bill is paid.
    await apply_debit_note(
        db_session, note_id=note.id, bill_id=bill.id, amount=Decimal("60")
    )
    refreshed = (await db_session.execute(select(Bill).where(Bill.id == bill.id))).scalar_one()
    assert Decimal(refreshed.amount_paid) == Decimal("100")
    assert refreshed.status == "paid"

    # And follow-up overdraft is rejected via the new bill-outstanding guard.
    note2 = await create_debit_note(
        db_session,
        vendor_id=vendor.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[
            {
                "description": "Return",
                "quantity": "1",
                "unit_price": "10",
                "account_id": accts["5400"].id,
            }
        ],
    )
    await issue_debit_note(db_session, note2.id)
    with pytest.raises(NoteError, match="bill outstanding"):
        await apply_debit_note(
            db_session, note_id=note2.id, bill_id=bill.id, amount=Decimal("5")
        )
