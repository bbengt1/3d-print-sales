from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BillableExpense(Base):
    """#263 P2: an expense incurred by the operator that should be re-billed
    to a customer (typically pass-through with optional markup).

    Lifecycle:
      - `pending` → operator marked an expense as billable to a customer
      - `invoiced` → the expense was added as a line on an invoice; the
        invoice id is captured here for traceability
      - `voided` → operator decided not to rebill

    Posting flow (#263 design): on `invoice` action, post Dr the
    customer-billable holding account / Cr the original expense account
    for `cost`, plus Dr Holding / Cr Income for the markup. Net effect:
    expense reduced, holding cleared by the invoice's AR side, markup
    booked as income. For Phase 2A we only persist the linkage; the JE
    posting is left to the operator (or to the broader sales-side rewrite
    in #317).
    """

    __tablename__ = "billable_expenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bills.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(255))
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    markup_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0)
    incurred_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
