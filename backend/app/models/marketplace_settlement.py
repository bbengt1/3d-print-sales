from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MarketplaceSettlement(Base):
    __tablename__ = "marketplace_settlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    settlement_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_channels.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    payout_date: Mapped[date] = mapped_column(Date)
    gross_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    marketplace_fees: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    adjustments: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reserves_held: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    net_deposit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    expected_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discrepancy_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    channel = relationship("SalesChannel")
    lines = relationship("SettlementLine", back_populates="settlement", cascade="all, delete-orphan")
