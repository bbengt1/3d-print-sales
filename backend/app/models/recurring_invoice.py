from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RecurringInvoice(Base):
    """A scheduled rule that auto-generates a sales invoice on a cadence
    (#247). Mirrors the cron-driven RecurringExpense pattern but on the
    AR side.
    """

    __tablename__ = "recurring_invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    cadence: Mapped[str] = mapped_column(String(20), default="monthly")
    interval_count: Mapped[int] = mapped_column(Integer, default=1)
    start_on: Mapped[date] = mapped_column(Date)
    next_run_on: Mapped[date] = mapped_column(Date, index=True)
    last_run_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    auto_email: Mapped[bool] = mapped_column(Boolean, default=False)
    line_items_template: Mapped[list] = mapped_column(JSON, default=list)
    due_in_days: Mapped[int] = mapped_column(Integer, default=30)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    runs = relationship("RecurringInvoiceRun", back_populates="recurring_invoice", cascade="all, delete-orphan")


class RecurringInvoiceRun(Base):
    """Audit row for each cron / manual run of a RecurringInvoice."""

    __tablename__ = "recurring_invoice_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recurring_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recurring_invoices.id", ondelete="CASCADE"), index=True
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))  # succeeded | failed | skipped
    generated_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(20))  # cron | manual_run_now | manual_skip
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    recurring_invoice = relationship("RecurringInvoice", back_populates="runs")
