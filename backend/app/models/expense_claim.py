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


class ExpenseClaim(Base):
    """An owner-paid (or contractor-fronted) reimbursable expense claim
    (#251). Lifecycle: draft → submitted → approved → reimbursed →
    cancelled. JE posts on approve.
    """

    __tablename__ = "expense_claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    claim_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    payer_kind: Mapped[str] = mapped_column(String(30), default="owner")  # owner | employee | contractor
    payer_name: Mapped[str] = mapped_column(String(200))
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    reimbursement_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
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

    lines = relationship("ExpenseClaimLine", back_populates="claim", cascade="all, delete-orphan")


class ExpenseClaimLine(Base):
    __tablename__ = "expense_claim_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expense_claims.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(255))
    expense_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # #324 P2: optional mileage tracking. When `miles` is non-null, the
    # service computes amount = miles * rate (rate captured at submit time
    # from `expense_claims.mileage_rate_per_mile` setting).
    line_kind: Mapped[str] = mapped_column(String(20), default="expense")  # expense | mileage
    miles: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    mileage_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    claim = relationship("ExpenseClaim", back_populates="lines")
