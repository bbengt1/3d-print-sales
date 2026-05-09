from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StatementImport(Base):
    """One uploaded bank statement file (#240). Parses into StatementLine
    rows that the operator then matches to existing journal lines or
    creates new transactions from.
    """

    __tablename__ = "statement_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    source_format: Mapped[str] = mapped_column(String(10))  # ofx | csv
    source_filename: Mapped[str] = mapped_column(String(255))
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True)
    imported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
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

    lines = relationship("StatementLine", back_populates="import_", cascade="all, delete-orphan")


class StatementLine(Base):
    """One row from an uploaded statement. Polymorphically tied to a
    journal line via `matched_journal_line_id` once the operator
    matches or creates a transaction.
    """

    __tablename__ = "statement_lines"
    __table_args__ = (
        UniqueConstraint("account_id", "fitid", name="uq_statement_lines_account_fitid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("statement_imports.id", ondelete="CASCADE"), index=True
    )
    # Denormalized so dedup uniqueness can be (account_id, fitid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    posted_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    description: Mapped[str] = mapped_column(String(500))
    fitid: Mapped[str | None] = mapped_column(String(120), nullable=True)
    matched_journal_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_lines.id"), nullable=True
    )
    match_status: Mapped[str] = mapped_column(String(20), default="unmatched", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    import_ = relationship("StatementImport", back_populates="lines")
