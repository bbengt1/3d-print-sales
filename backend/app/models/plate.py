from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Plate(Base):
    __tablename__ = "plates"
    __table_args__ = (
        UniqueConstraint("job_id", "plate_number", name="uq_plates_job_plate_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plate_number: Mapped[int] = mapped_column(Integer, nullable=False)
    printer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("printers.id"), nullable=True, index=True
    )
    parts_count: Mapped[int] = mapped_column(Integer, nullable=False)
    material_g: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    print_time_hrs: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    job = relationship("Job", back_populates="plates")
    printer = relationship("Printer")
