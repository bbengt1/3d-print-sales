from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaxRemittance(Base):
    __tablename__ = "tax_remittances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tax_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tax_profiles.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    remittance_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tax_profile = relationship("TaxProfile")
