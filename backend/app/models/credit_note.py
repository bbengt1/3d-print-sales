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


class CreditNote(Base):
    """Customer-facing return/refund document (#248)."""

    __tablename__ = "credit_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    credit_note_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    original_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True, index=True
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

    lines = relationship("CreditNoteLine", back_populates="credit_note", cascade="all, delete-orphan")
    applications = relationship("CreditNoteApplication", back_populates="credit_note", cascade="all, delete-orphan")


class CreditNoteLine(Base):
    __tablename__ = "credit_note_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    credit_note = relationship("CreditNote", back_populates="lines")


class CreditNoteApplication(Base):
    __tablename__ = "credit_note_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="CASCADE"), index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    applied_on: Mapped[date] = mapped_column(Date)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    credit_note = relationship("CreditNote", back_populates="applications")
