from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StatementMatchRule(Base):
    """Rule that auto-handles imported statement lines (#241).

    Phase 1 supports the `ignore` action only — fully matches a known
    description pattern and skips the line from review. Phase 2 will
    add `create_receipt` / `create_payment` actions that auto-post JEs.
    """

    __tablename__ = "statement_match_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    match_type: Mapped[str] = mapped_column(String(20))  # contains | regex
    match_pattern: Mapped[str] = mapped_column(String(500))
    match_amount_sign: Mapped[str] = mapped_column(String(10), default="any")  # debit | credit | any
    action: Mapped[str] = mapped_column(String(30))  # ignore (Phase 1) | create_receipt / create_payment (Phase 2)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
