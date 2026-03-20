from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_channels.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    shipping_charged: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    platform_fees: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    tax_collected: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    net_revenue: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    customer = relationship("Customer")
    channel = relationship("SalesChannel")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
