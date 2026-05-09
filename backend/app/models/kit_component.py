from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KitComponent(Base):
    """Links a 'kit' product to its component products with per-unit
    quantities (#262). A product is treated as a kit whenever it has at
    least one row here — no extra `kind` column on Product needed.
    """

    __tablename__ = "kit_components"
    __table_args__ = (
        UniqueConstraint("kit_product_id", "component_product_id", name="uq_kit_components_kit_component"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kit_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    component_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
