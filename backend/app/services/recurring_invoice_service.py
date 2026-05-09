"""Recurring sales invoice service (#247).

Cron-driven (external n8n calls /run-due daily). Snapshot pricing:
each generated invoice copies `line_items_template` verbatim. On
generation failure the schedule does NOT advance, surfacing the error
on the recurring-invoice row until the operator fixes the underlying
issue and clicks Run-Now.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.recurring_invoice import RecurringInvoice, RecurringInvoiceRun
from app.services.reference_number_service import next_number


class RecurringInvoiceError(RuntimeError):
    pass


def _last_day_of_month(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def advance_date(d: date, cadence: str, interval_count: int) -> date:
    """Compute next-run date per cadence math.

    monthly + N: add N months, preserving day-of-month with month-end fallback.
    yearly + N: add N years, with Feb 29 → Feb 28 in non-leap years.
    weekly + N: add N*7 days.
    daily + N: add N days.
    """
    if cadence == "daily":
        from datetime import timedelta
        return d + timedelta(days=interval_count)
    if cadence == "weekly":
        from datetime import timedelta
        return d + timedelta(weeks=interval_count)
    if cadence == "monthly":
        total = d.year * 12 + (d.month - 1) + interval_count
        y, m = divmod(total, 12)
        last = calendar.monthrange(y, m + 1)[1]
        return date(y, m + 1, min(d.day, last))
    if cadence == "yearly":
        target_year = d.year + interval_count
        last = calendar.monthrange(target_year, d.month)[1]
        return date(target_year, d.month, min(d.day, last))
    raise RecurringInvoiceError(f"Unknown cadence: {cadence}")


async def run_one(
    db: AsyncSession,
    *,
    recurring_id: uuid.UUID,
    triggered_by: str = "manual_run_now",
) -> RecurringInvoiceRun:
    """Generate one invoice for the given recurring rule and advance the
    schedule on success. Persist a `RecurringInvoiceRun` audit row.
    """
    ri = (await db.execute(select(RecurringInvoice).where(RecurringInvoice.id == recurring_id))).scalar_one_or_none()
    if ri is None:
        raise RecurringInvoiceError("Recurring invoice not found")
    if not ri.is_active:
        raise RecurringInvoiceError("Recurring invoice is paused")

    target_date = ri.next_run_on
    try:
        invoice = await _generate_invoice(db, ri, target_date)
    except Exception as e:  # noqa: BLE001
        ri.last_error = f"{type(e).__name__}: {e}"
        ri.last_failed_at = datetime.now(timezone.utc)
        run = RecurringInvoiceRun(
            recurring_invoice_id=ri.id,
            target_date=target_date,
            status="failed",
            error=ri.last_error,
            triggered_by=triggered_by,
        )
        db.add(run)
        await db.flush()
        return run

    next_due = advance_date(target_date, ri.cadence, ri.interval_count)
    ri.last_run_on = target_date
    ri.next_run_on = next_due
    ri.last_error = None
    ri.last_failed_at = None
    if ri.end_on is not None and next_due > ri.end_on:
        ri.is_active = False

    run = RecurringInvoiceRun(
        recurring_invoice_id=ri.id,
        target_date=target_date,
        status="succeeded",
        generated_invoice_id=invoice.id,
        triggered_by=triggered_by,
    )
    db.add(run)
    await db.flush()
    return run


async def skip_next(db: AsyncSession, recurring_id: uuid.UUID) -> RecurringInvoiceRun:
    ri = (await db.execute(select(RecurringInvoice).where(RecurringInvoice.id == recurring_id))).scalar_one_or_none()
    if ri is None:
        raise RecurringInvoiceError("Recurring invoice not found")
    target_date = ri.next_run_on
    next_due = advance_date(target_date, ri.cadence, ri.interval_count)
    ri.last_run_on = target_date
    ri.next_run_on = next_due
    if ri.end_on is not None and next_due > ri.end_on:
        ri.is_active = False
    run = RecurringInvoiceRun(
        recurring_invoice_id=ri.id,
        target_date=target_date,
        status="skipped",
        triggered_by="manual_skip",
    )
    db.add(run)
    await db.flush()
    return run


async def run_due(db: AsyncSession, *, today: date | None = None) -> dict:
    """Cron entry point. Generates invoices for every active rule whose
    `next_run_on` has come due. Idempotent within a day on success: a
    second call finds nothing further due. Failures stay due so the next
    cron tick retries.
    """
    today = today or datetime.now(timezone.utc).date()
    rules = (
        await db.execute(
            select(RecurringInvoice).where(
                RecurringInvoice.is_active == True,  # noqa: E712
                RecurringInvoice.next_run_on <= today,
            )
        )
    ).scalars().all()

    succeeded = 0
    failed = 0
    for r in rules:
        run = await run_one(db, recurring_id=r.id, triggered_by="cron")
        if run.status == "succeeded":
            succeeded += 1
        else:
            failed += 1
    return {"succeeded": succeeded, "failed": failed, "considered": len(rules)}


async def _generate_invoice(
    db: AsyncSession, ri: RecurringInvoice, issue_date: date
) -> Invoice:
    """Build a real Invoice from the recurring template."""
    from datetime import timedelta

    template_lines = list(ri.line_items_template or [])
    if not template_lines:
        raise RecurringInvoiceError("Template has no line items")

    invoice_number = await next_number(db, "invoice")
    due_date = issue_date + timedelta(days=int(ri.due_in_days or 30))

    # Pre-compute totals so we don't depend on the post-flush invoice
    # service helpers.
    subtotal = Decimal("0")
    for line in template_lines:
        qty = Decimal(str(line.get("quantity", 0)))
        price = Decimal(str(line.get("unit_price", 0)))
        subtotal += qty * price
    subtotal = subtotal.quantize(Decimal("0.01"))
    total_due = subtotal  # tax/shipping deferred to manual edit

    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=ri.customer_id,
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=total_due,
        amount_paid=Decimal("0"),
        balance_due=total_due,
        notes=ri.notes,
        status="draft",
    )
    db.add(invoice)
    await db.flush()

    for line in template_lines:
        qty_int = int(line.get("quantity", 0))
        price = Decimal(str(line.get("unit_price", 0)))
        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                description=line.get("description", ""),
                quantity=qty_int,
                unit_price=price,
                line_total=Decimal(qty_int) * price,
                notes=line.get("notes"),
            )
        )
    await db.flush()
    return invoice
