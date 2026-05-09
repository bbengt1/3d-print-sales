from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomFieldDefinition(Base):
    """User-defined field for a record scope (#253). Phase 1 stores values
    in a separate `custom_field_values` table to avoid migrating every
    scoped record table; the existing per-record record stays unchanged.
    """

    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_custom_field_definitions_scope_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(64))  # slug used in API + filters
    name: Mapped[str] = mapped_column(String(120))  # display label
    # text | long_text | number | date | dropdown | checkbox
    field_type: Mapped[str] = mapped_column(String(20))
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # for dropdown
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CustomFieldValue(Base):
    """One value per `(definition, record_id)`. String-stored — coerced on
    read per the definition's `field_type`."""

    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint("definition_id", "record_id", name="uq_custom_field_values_def_record"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
