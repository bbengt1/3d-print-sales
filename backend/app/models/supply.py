from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Supply(Base):
    __tablename__ = "supplies"
    __table_args__ = (UniqueConstraint("sku", name="uq_supplies_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="each")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    reorder_point: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
