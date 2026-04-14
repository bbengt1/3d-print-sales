from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DB
from app.schemas.insight import InsightRequest, InsightStatusResponse, InsightSummaryResponse
from app.services.ai_insights_service import (
    AIInsightConfigurationError,
    AIInsightProviderError,
    generate_insight_summary,
    get_ai_status,
)

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get(
    "/status",
    response_model=InsightStatusResponse,
    summary="Get AI insights provider status",
    description="Returns the selected LLM provider, active model, and whether the provider is configured for read-only insights.",
)
async def get_insights_status(user: CurrentUser, db: DB):
    return await get_ai_status(db)


@router.post(
    "/summary",
    response_model=InsightSummaryResponse,
    summary="Generate AI business insights",
    description="Uses the configured LLM provider to generate a read-only operational summary grounded in app data.",
)
async def create_insight_summary(body: InsightRequest, user: CurrentUser, db: DB):
    try:
        return await generate_insight_summary(db, question=body.question)
    except AIInsightConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIInsightProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
