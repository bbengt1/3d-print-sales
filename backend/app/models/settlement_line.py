from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SettlementLine(Base):
    __tablename__ = "settlement_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    settlement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marketplace_settlements.id"), index=True)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sales.id"), nullable=True, index=True)
    line_type: Mapped[str] = mapped_column(String(30), default="sale")
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    settlement = relationship("MarketplaceSettlement", back_populates="lines")
    sale = relationship("Sale")
