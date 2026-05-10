from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FormTemplate(Base):
    """#331 P2: per-doctype form preset.

    Operators can save the values they always re-type into a particular
    create form (default tax_profile, terms, notes, due_in_days, etc.) as
    a named template, then load it before submitting.

    `scope` is one of: invoice | quote | sales_order | purchase_order |
    bill | expense_claim | journal_entry. The `defaults` blob is opaque
    JSON — the frontend or service wrapping it is responsible for
    interpreting which keys map to which form fields.
    """

    __tablename__ = "form_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    defaults: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
