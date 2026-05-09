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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InterAccountTransfer(Base):
    """A movement of money between two of the business's own bank accounts.
    Always-posted model: a single JE with two journal lines carrying
    independent `posted_on` dates so each leg reconciles against the
    appropriate statement (#246).
    """

    __tablename__ = "inter_account_transfers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transfer_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    from_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    to_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    paid_on: Mapped[date] = mapped_column(Date)
    received_on: Mapped[date] = mapped_column(Date)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
