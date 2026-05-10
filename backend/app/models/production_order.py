from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductionOrder(Base):
    """Closes the loop between operational job tracking and inventory
    accounting (#242). At create time we snapshot the product's BOM into
    `ProductionOrderConsumption` rows; at close-out we FIFO-consume the
    snapshot quantities from `material_receipts` (matching the existing
    inventory_accounting_service pattern), post a balanced JE
    Cr Material Inventory / Dr Finished Goods, and create a
    `FinishedGoodsLayer` row capturing the produced units' unit cost.
    """

    __tablename__ = "production_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    output_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_material_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    applied_overhead: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    total_finished_goods_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
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

    consumptions = relationship(
        "ProductionOrderConsumption",
        back_populates="production_order",
        cascade="all, delete-orphan",
    )


class ProductionOrderConsumption(Base):
    """Snapshot of a single BOM line for a production order.

    Phase 1 stores material consumption only — supply consumption is
    snapshotted but not used for FIFO drawdown. `actual_qty` defaults
    to the planned quantity at close-out and is editable by operator
    (Phase 2 follow-up wires the editor).
    """

    __tablename__ = "production_order_consumptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    production_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("production_orders.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # material | supply | product
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    supply_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplies.id"), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    actual_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    actual_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    actual_total_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    production_order = relationship("ProductionOrder", back_populates="consumptions")


class FinishedGoodsLayer(Base):
    """One layer per closed production order's output (#242). Sales-side
    COGS will FIFO-draw from these layers in Phase 2. Phase 1 just creates
    them and reports `qty_remaining`.
    """

    __tablename__ = "finished_goods_layers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    production_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("production_orders.id"), nullable=True, index=True
    )
    qty_total: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
