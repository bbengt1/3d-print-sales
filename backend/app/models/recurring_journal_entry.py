from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

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


class RecurringJournalEntry(Base):
    """Scheduled JE rule (#260). Mirrors the cron-driven RecurringInvoice
    pattern but generates JournalEntry rows from a `lines_template` JSONB
    snapshot instead of an Invoice + lines.
    """

    __tablename__ = "recurring_journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), index=True)
    cadence: Mapped[str] = mapped_column(String(20), default="monthly")
    interval_count: Mapped[int] = mapped_column(Integer, default=1)
    start_on: Mapped[date] = mapped_column(Date)
    next_run_on: Mapped[date] = mapped_column(Date, index=True)
    last_run_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    lines_template: Mapped[list] = mapped_column(JSON, default=list)
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

    runs = relationship(
        "RecurringJournalEntryRun",
        back_populates="recurring_je",
        cascade="all, delete-orphan",
    )


class RecurringJournalEntryRun(Base):
    __tablename__ = "recurring_journal_entry_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recurring_je_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recurring_journal_entries.id", ondelete="CASCADE"), index=True
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    generated_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    recurring_je = relationship("RecurringJournalEntry", back_populates="runs")
