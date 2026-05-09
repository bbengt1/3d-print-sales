from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReferenceSequence(Base):
    """Per-(scope, year) monotonically-increasing counter.

    Backs `app.services.reference_number_service.next_number` which atomically
    increments `last_value` via INSERT ... ON CONFLICT on PostgreSQL (or a
    SELECT FOR UPDATE-style fallback on SQLite during tests).
    """

    __tablename__ = "reference_sequences"
    __table_args__ = (
        UniqueConstraint("scope", "year", name="uq_reference_sequences_scope_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(50), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
