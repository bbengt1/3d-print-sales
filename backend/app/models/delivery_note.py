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


class DeliveryNote(Base):
    """Numbered delivery / dispatch document, separate from invoice (#263).
    Tracks shipped quantities per line so partial dispatches against an
    invoice are visible.
    """

    __tablename__ = "delivery_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_note_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issued_on: Mapped[date] = mapped_column(Date)
    shipped_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    lines = relationship("DeliveryNoteLine", back_populates="delivery_note", cascade="all, delete-orphan")


class DeliveryNoteLine(Base):
    __tablename__ = "delivery_note_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("delivery_notes.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    delivery_note = relationship("DeliveryNote", back_populates="lines")
