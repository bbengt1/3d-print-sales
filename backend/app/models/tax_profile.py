from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaxProfile(Base):
    __tablename__ = "tax_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(120))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0)
    filing_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_marketplace_facilitated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Compound + reverse-charge support (#258).
    is_compound: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reverse_charge: Mapped[bool] = mapped_column(Boolean, default=False)
    receivable_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    components = relationship(
        "TaxProfileComponent",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="TaxProfileComponent.apply_order",
    )


class TaxProfileComponent(Base):
    """Sequential tax component for a compound profile (#258).

    Each component applies to the running base = original_base + sum of
    prior components' tax amounts. `apply_order` is 0-indexed.
    """

    __tablename__ = "tax_profile_components"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tax_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    apply_order: Mapped[int] = mapped_column(Integer, default=0)
    liability_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    profile = relationship("TaxProfile", back_populates="components")
