from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RefundRequestBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)


class ApprovalDecisionBody(BaseModel):
    decision_notes: str | None = Field(None, max_length=500)


class ApprovalRequestResponse(BaseModel):
    id: uuid.UUID
    action_type: str
    entity_type: str
    entity_id: str | None = None
    requested_by_user_id: uuid.UUID
    approved_by_user_id: uuid.UUID | None = None
    status: str
    reason: str
    request_payload: dict
    decision_notes: str | None = None
    created_at: datetime.datetime
    decided_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)
