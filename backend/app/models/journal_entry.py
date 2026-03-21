from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entry_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    accounting_period_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_periods.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_reversal: Mapped[bool] = mapped_column(Boolean, default=False)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    accounting_period = relationship("AccountingPeriod", back_populates="journal_entries")
    lines = relationship("JournalLine", back_populates="journal_entry", cascade="all, delete-orphan")
    reversal_of = relationship("JournalEntry", remote_side=[id])
