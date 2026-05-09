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


class FixedAsset(Base):
    """A capital asset on the balance sheet — typically a printer, camera,
    or computer — with acquisition cost, useful life, depreciation schedule,
    and disposal accounting (#238).

    Status lifecycle: active → fully_depreciated (auto when book value
    reaches salvage) → optionally disposed (operator action).
    """

    __tablename__ = "fixed_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), index=True)
    asset_tag: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acquired_on: Mapped[date] = mapped_column(Date)
    acquisition_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    useful_life_months: Mapped[int] = mapped_column(Integer)
    # straight_line | declining_balance
    depreciation_method: Mapped[str] = mapped_column(String(30), default="straight_line")
    # Optional explicit DB rate as a fraction (e.g. 0.40 for 40%/year).
    # When None and method=declining_balance, defaults to 2/(life_years) (DDB).
    declining_balance_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    asset_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    accumulated_depreciation_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    depreciation_expense_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    disposed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    disposal_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    acquisition_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bills.id"), nullable=True
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

    depreciation_entries = relationship(
        "DepreciationEntry",
        back_populates="fixed_asset",
        cascade="all, delete-orphan",
    )


class DepreciationEntry(Base):
    """One month of depreciation for one fixed asset, with the resulting
    journal entry id for full audit. Idempotent per `(fixed_asset, period_end)`.
    """

    __tablename__ = "depreciation_entries"
    __table_args__ = (
        UniqueConstraint(
            "fixed_asset_id", "period_end",
            name="uq_depreciation_entries_asset_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fixed_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixed_assets.id", ondelete="CASCADE"), index=True
    )
    period_end: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    fixed_asset = relationship("FixedAsset", back_populates="depreciation_entries")
