from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotes.id"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credits_applied: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer")
    quote = relationship("Quote")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
