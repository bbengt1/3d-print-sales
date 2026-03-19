from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200))
    qty_per_plate: Mapped[int] = mapped_column(Integer)
    num_plates: Mapped[int] = mapped_column(Integer)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"))
    total_pieces: Mapped[int] = mapped_column(Integer)
    material_per_plate_g: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    print_time_per_plate_hrs: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    labor_mins: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    design_time_hrs: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, default=0
    )

    # Computed cost fields
    electricity_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    design_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    machine_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    packaging_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    failure_buffer: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    subtotal_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    overhead: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    target_margin_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=40)
    price_per_piece: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    platform_fees: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    net_profit: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    profit_per_piece: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)

    status: Mapped[str] = mapped_column(String(20), default="completed")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    customer = relationship("Customer", back_populates="jobs")
    material = relationship("Material")
