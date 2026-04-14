from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field


AIProvider = Literal["chatgpt", "claude", "grok"]
InsightPriority = Literal["high", "medium", "low"]


class InsightRequest(BaseModel):
    question: str | None = Field(
        None,
        max_length=500,
        description="Optional operator question to steer the insight summary.",
    )


class InsightEvidenceMetric(BaseModel):
    key: str
    label: str
    value: str


class InsightItem(BaseModel):
    title: str
    detail: str
    priority: InsightPriority = "medium"
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str | None = None


class InsightStatusResponse(BaseModel):
    provider: AIProvider
    model: str
    configured: bool
    available_providers: list[AIProvider]
    note: str


class InsightSummaryResponse(BaseModel):
    provider: AIProvider
    model: str
    generated_at: datetime.datetime
    title: str
    summary: str
    question: str | None = None
    recommendations: list[InsightItem]
    risks: list[InsightItem]
    suggested_questions: list[str]
    evidence_metrics: list[InsightEvidenceMetric]
    read_only: bool = True
