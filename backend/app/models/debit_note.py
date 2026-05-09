from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebitNote(Base):
    """Vendor-facing return document (#248). Symmetric mirror of CreditNote."""

    __tablename__ = "debit_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    debit_note_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    original_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bills.id"), nullable=True, index=True
    )
    issued_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
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

    lines = relationship("DebitNoteLine", back_populates="debit_note", cascade="all, delete-orphan")
    applications = relationship("DebitNoteApplication", back_populates="debit_note", cascade="all, delete-orphan")


class DebitNoteLine(Base):
    __tablename__ = "debit_note_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    debit_note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("debit_notes.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    debit_note = relationship("DebitNote", back_populates="lines")


class DebitNoteApplication(Base):
    __tablename__ = "debit_note_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    debit_note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("debit_notes.id", ondelete="CASCADE"), index=True
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bills.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    applied_on: Mapped[date] = mapped_column(Date)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    debit_note = relationship("DebitNote", back_populates="applications")
