from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    brand: Mapped[str] = mapped_column(String(100))
    spool_weight_g: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    spool_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    net_usable_g: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    cost_per_g: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    spools_in_stock: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, default=2)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    receipts = relationship("MaterialReceipt", back_populates="material", cascade="all, delete-orphan")
