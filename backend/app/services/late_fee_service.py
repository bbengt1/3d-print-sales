"""#263 P2: late-payment-fee invoice generation.

Cron entry point. Walks every open invoice past `due_date + grace`, posts
a follow-up draft invoice with one `LATE FEE` line equal to
`balance_due * rate_pct / 100`. Idempotent within a calendar day:
rerunning the same day re-uses the same invoice number bookkeeping (we
gate on whether a fee invoice for the same source invoice already exists
issued on today's date).

Per-customer override on `Customer.late_payment_fee_rate_pct` /
`late_payment_fee_grace_days`; falls back to global settings:
- `late_payment_fee_rate_pct` (e.g. "1.5")
- `late_payment_fee_grace_days` (e.g. "10")

If neither customer-level nor global rate is set, the cron skips the
customer (no fee charged).
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.setting import Setting
from app.services.reference_number_service import next_number


SOURCE_TYPE = "late_fee_for_invoice"


def _derive_balance(invoice: Invoice) -> Decimal:
    return Decimal(invoice.balance_due or 0)


async def _global_setting(db: AsyncSession, key: str) -> str | None:
    row = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
    if row is None or not row.value:
        return None
    return row.value.strip()


async def _resolve_terms(
    db: AsyncSession, customer: Customer | None
) -> tuple[Decimal | None, int]:
    """Returns (rate_pct, grace_days). rate_pct may be None → no fee."""
    rate: Decimal | None = None
    grace = 0
    if customer is not None:
        if customer.late_payment_fee_rate_pct is not None:
            rate = Decimal(customer.late_payment_fee_rate_pct)
        if customer.late_payment_fee_grace_days is not None:
            grace = int(customer.late_payment_fee_grace_days)
    if rate is None:
        global_rate = await _global_setting(db, "late_payment_fee_rate_pct")
        if global_rate:
            try:
                rate = Decimal(global_rate)
            except Exception:
                rate = None
    if grace == 0:
        global_grace = await _global_setting(db, "late_payment_fee_grace_days")
        if global_grace:
            try:
                grace = int(global_grace)
            except Exception:
                grace = 0
    return rate, grace


async def _existing_fee_invoice_today(
    db: AsyncSession, source_invoice_id: str, today: datetime.date
) -> Invoice | None:
    rows = (
        await db.execute(
            select(Invoice).where(
                Invoice.is_deleted == False,  # noqa: E712
                Invoice.notes.like(f"%[late-fee-source:{source_invoice_id}]%"),
                Invoice.issue_date == today,
            )
        )
    ).scalars().all()
    return rows[0] if rows else None


async def run_late_fees_due(
    db: AsyncSession, *, today: datetime.date | None = None
) -> dict:
    today = today or datetime.date.today()
    invoices = (
        await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.lines))
            .where(
                and_(
                    Invoice.is_deleted == False,  # noqa: E712
                    Invoice.status != "void",
                    Invoice.balance_due > 0,
                )
            )
        )
    ).scalars().all()

    generated: list[dict] = []
    skipped = 0

    for inv in invoices:
        if inv.due_date is None:
            skipped += 1
            continue
        customer = None
        if inv.customer_id is not None:
            customer = (
                await db.execute(select(Customer).where(Customer.id == inv.customer_id))
            ).scalar_one_or_none()
        rate, grace = await _resolve_terms(db, customer)
        if rate is None or rate <= 0:
            skipped += 1
            continue
        cutoff = inv.due_date + datetime.timedelta(days=grace)
        if today <= cutoff:
            skipped += 1
            continue
        # Idempotency: skip if we already generated a fee invoice today for this source.
        if await _existing_fee_invoice_today(db, str(inv.id), today):
            skipped += 1
            continue

        balance = _derive_balance(inv)
        fee_amount = (balance * rate / Decimal(100)).quantize(Decimal("0.01"))
        if fee_amount <= 0:
            skipped += 1
            continue

        fee_number = await next_number(db, "invoice")
        fee_invoice = Invoice(
            invoice_number=fee_number,
            customer_id=inv.customer_id,
            customer_name=inv.customer_name,
            issue_date=today,
            due_date=today + datetime.timedelta(days=15),
            subtotal=fee_amount,
            tax_amount=Decimal("0"),
            shipping_amount=Decimal("0"),
            credits_applied=Decimal("0"),
            total_due=fee_amount,
            amount_paid=Decimal("0"),
            balance_due=fee_amount,
            status="draft",
            notes=(
                f"Late payment fee for invoice {inv.invoice_number} "
                f"(balance ${balance:.2f} × {rate}% past due {today - cutoff} days). "
                f"[late-fee-source:{inv.id}]"
            ),
        )
        db.add(fee_invoice)
        await db.flush()
        db.add(
            InvoiceLine(
                invoice_id=fee_invoice.id,
                description=f"LATE FEE — invoice {inv.invoice_number}",
                quantity=1,
                unit_price=fee_amount,
                line_total=fee_amount,
            )
        )
        generated.append(
            {
                "source_invoice_id": str(inv.id),
                "fee_invoice_id": str(fee_invoice.id),
                "fee_invoice_number": fee_number,
                "fee_amount": str(fee_amount),
            }
        )

    await db.flush()
    return {
        "today": today.isoformat(),
        "generated": generated,
        "generated_count": len(generated),
        "skipped": skipped,
    }
