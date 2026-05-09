from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class IntangibleAsset(Base):
    """Symmetric mirror of FixedAsset for intangibles — CAD/slicer
    subscriptions amortized over their term, asset packs, brand/domain
    purchases, multi-year listing fees. #252.

    Same lifecycle: active → fully_amortized (auto when book reaches 0)
    → optionally disposed.
    """

    __tablename__ = "intangible_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), index=True)
    asset_tag: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acquired_on: Mapped[date] = mapped_column(Date)
    acquisition_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    useful_life_months: Mapped[int] = mapped_column(Integer)
    amortization_method: Mapped[str] = mapped_column(String(30), default="straight_line")
    declining_balance_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    asset_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    accumulated_amortization_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    amortization_expense_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    disposed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    disposal_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    amortization_entries = relationship(
        "AmortizationEntry",
        back_populates="intangible_asset",
        cascade="all, delete-orphan",
    )


class AmortizationEntry(Base):
    __tablename__ = "amortization_entries"
    __table_args__ = (
        UniqueConstraint(
            "intangible_asset_id", "period_end",
            name="uq_amortization_entries_asset_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    intangible_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intangible_assets.id", ondelete="CASCADE"), index=True
    )
    period_end: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    intangible_asset = relationship("IntangibleAsset", back_populates="amortization_entries")
