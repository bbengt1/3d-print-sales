"""#263 P2: customer-side withholding tax handling.

When a payment is received against a withholding-customer's invoice, the
gross amount is split into (cash received) + (withheld portion). The
withheld portion is posted as a credit to the customer's withholding
profile's liability account; cash and AR balance against gross.

JE shape:
  Dr Cash account              (gross - withheld)
  Dr Withholding Asset (1100?) ← withheld portion lives in liability
                                  account specified by the profile
  Cr AR (1100)                 gross

The operator remits the withheld liability later via the existing
`tax_remittance` flow. This module is invoked explicitly via the
`apply-payment-with-withholding` endpoint; the regular `apply-payment`
path stays JE-free for backwards compatibility.
"""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.withholding_profile import WithholdingProfile
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import create_journal_entry


class WithholdingError(RuntimeError):
    pass


async def apply_payment_with_withholding(
    db: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    gross_amount: Decimal,
    cash_account_id: uuid.UUID,
    paid_on: datetime.date | None = None,
) -> dict:
    """Apply a payment that has had withholding deducted at the customer side.

    `gross_amount` is the AR-side amount being cleared (i.e. invoice
    paid-down by). Cash actually received = gross - withheld.
    """
    paid_on = paid_on or datetime.date.today()
    invoice = (
        await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    ).scalar_one_or_none()
    if invoice is None:
        raise WithholdingError("Invoice not found")
    if invoice.customer_id is None:
        raise WithholdingError("Cannot apply withholding payment to a customerless invoice")
    customer = (
        await db.execute(select(Customer).where(Customer.id == invoice.customer_id))
    ).scalar_one()
    if customer.withholding_profile_id is None:
        raise WithholdingError("Customer has no withholding profile attached")
    profile = (
        await db.execute(
            select(WithholdingProfile).where(WithholdingProfile.id == customer.withholding_profile_id)
        )
    ).scalar_one()

    rate = Decimal(profile.rate_pct)
    if rate <= 0:
        raise WithholdingError("Withholding rate must be > 0")

    withheld = (Decimal(gross_amount) * rate / Decimal(100)).quantize(Decimal("0.01"))
    cash_received = (Decimal(gross_amount) - withheld).quantize(Decimal("0.01"))

    ar = (
        await db.execute(select(Account).where(Account.code == "1100"))
    ).scalar_one_or_none()
    if ar is None:
        raise WithholdingError("Accounts Receivable (1100) missing from COA")
    cash = (
        await db.execute(select(Account).where(Account.id == cash_account_id))
    ).scalar_one_or_none()
    if cash is None:
        raise WithholdingError("Cash account not found")
    liability = (
        await db.execute(select(Account).where(Account.id == profile.liability_account_id))
    ).scalar_one_or_none()
    if liability is None:
        raise WithholdingError("Withholding liability account not found")

    je = await create_journal_entry(
        db,
        JournalEntryCreate(
            entry_date=paid_on,
            source_type="invoice_payment_withholding",
            source_id=str(invoice.id),
            memo=f"Payment with withholding for invoice {invoice.invoice_number}",
            lines=[
                JournalLineCreate(
                    account_id=cash.id, entry_type="debit", amount=cash_received,
                    description=f"Cash received on {invoice.invoice_number}",
                ),
                JournalLineCreate(
                    account_id=liability.id, entry_type="debit", amount=withheld,
                    description=f"Withheld by customer on {invoice.invoice_number}",
                ),
                JournalLineCreate(
                    account_id=ar.id, entry_type="credit", amount=Decimal(gross_amount),
                    description=f"Clear AR for {invoice.invoice_number}",
                ),
            ],
        ),
    )

    payment = Payment(
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        payment_date=paid_on,
        amount=gross_amount,
        unapplied_amount=Decimal("0"),
    )
    db.add(payment)
    invoice.amount_paid = Decimal(invoice.amount_paid) + Decimal(gross_amount)
    invoice.balance_due = max(Decimal("0"), Decimal(invoice.balance_due) - Decimal(gross_amount))
    if invoice.balance_due == 0:
        invoice.status = "paid"
    elif invoice.amount_paid > 0:
        invoice.status = "partially_paid"
    await db.flush()
    return {
        "invoice_id": str(invoice.id),
        "journal_entry_id": str(je.id),
        "gross": str(Decimal(gross_amount)),
        "cash_received": str(cash_received),
        "withheld": str(withheld),
        "withholding_account_id": str(liability.id),
        "rate_pct": str(rate),
    }
