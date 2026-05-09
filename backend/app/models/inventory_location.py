from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InventoryLocation(Base):
    """Logical or physical bucket for inventory (workshop, packaging,
    consignment, marketplace FBA). #245.

    A `Default` location is auto-seeded so single-location operators see
    no UI changes; multi-location-aware screens flip on automatically when
    a second location is created.
    """

    __tablename__ = "inventory_locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # internal | consignment | marketplace
    kind: Mapped[str] = mapped_column(String(30), default="internal", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class InventoryTransfer(Base):
    """A movement of inventory items between two `InventoryLocation` rows.
    No GL impact — the inventory asset stays at the same total balance.

    Lifecycle: pending → in_transit (ship) → completed (receive).
    Cancellation is allowed from pending or in_transit; cancelling an
    in-transit transfer releases the source-side hold.
    """

    __tablename__ = "inventory_transfers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transfer_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    from_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_locations.id"))
    to_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_locations.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transferred_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
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

    lines = relationship("InventoryTransferLine", back_populates="transfer", cascade="all, delete-orphan")


class InventoryTransferLine(Base):
    __tablename__ = "inventory_transfer_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_transfers.id", ondelete="CASCADE"), index=True
    )
    # material | supply | product
    kind: Mapped[str] = mapped_column(String(20))
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    supply_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplies.id"), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    transfer = relationship("InventoryTransfer", back_populates="lines")
