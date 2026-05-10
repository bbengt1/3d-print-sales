from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BankImportMapping(Base):
    """#315 P2: per-bank-account CSV column mapping.

    When an operator imports a CSV from a particular bank, they shouldn't
    have to re-supply the column-name mapping every time. We persist one
    `BankImportMapping` per bank Account; future imports for that account
    automatically apply the saved mapping when no override is given.

    `mapping` is a flat dict where keys are the canonical fields the
    parser understands (`date`, `amount`, `description`, `fitid`) and
    values are the CSV column names from this bank's export.
    """

    __tablename__ = "bank_import_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, index=True
    )
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
