from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Printer(Base):
    __tablename__ = "printers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="idle", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    monitor_provider: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    monitor_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    monitor_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monitor_poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=30)
    monitor_online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    monitor_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    monitor_progress_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_print_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monitor_last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    monitor_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    monitor_bed_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    monitor_tool_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    monitor_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    monitor_last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
