from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WithholdingProfile(Base):
    """#263 P2: per-customer withholding tax profile.

    When a customer has a withholding profile attached and a payment is
    received against one of their invoices, the receipt service splits
    the gross amount into (cash received) + (withheld portion). The
    withheld portion is posted as a credit to `liability_account_id`,
    which the operator later remits to the tax authority via the
    existing tax_remittance flow.
    """

    __tablename__ = "withholding_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    liability_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
