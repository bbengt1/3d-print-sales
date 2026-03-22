from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MaterialReceipt(Base):
    __tablename__ = "material_receipts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), index=True)
    vendor_name: Mapped[str] = mapped_column(String(120), index=True)
    purchase_date: Mapped[date] = mapped_column(Date, index=True)
    receipt_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    quantity_purchased_g: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity_remaining_g: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_cost_per_g: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    landed_cost_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    landed_cost_per_g: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valuation_method: Mapped[str] = mapped_column(String(20), default="lot")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    material = relationship("Material", back_populates="receipts")
