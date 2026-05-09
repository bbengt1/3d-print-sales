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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BankReconciliation(Base):
    """One reconciliation = one operator pass against one bank account's
    statement-end balance. Lifecycle: in_progress → finalized; an admin can
    reopen a finalized reconciliation back to in_progress (#239).
    """

    __tablename__ = "bank_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    statement_end_date: Mapped[date] = mapped_column(Date)
    statement_ending_balance: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
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

    lines = relationship("BankReconciliationLine", back_populates="reconciliation", cascade="all, delete-orphan")


class BankReconciliationLine(Base):
    """A `(reconciliation, journal_line)` link recording that the operator
    matched this journal line to the statement during this reconciliation.
    Snapshots `amount` for tamper detection.
    """

    __tablename__ = "bank_reconciliation_lines"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_id", "journal_line_id",
            name="uq_bank_reconciliation_lines_recon_line",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_reconciliations.id", ondelete="CASCADE"), index=True
    )
    journal_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_lines.id"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    reconciliation = relationship("BankReconciliation", back_populates="lines")
