from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    entity_type: str
    entity_id: str
    action: str
    reason: str | None = None
    before_snapshot: dict | None = None
    after_snapshot: dict | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
