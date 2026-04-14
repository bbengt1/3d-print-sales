from __future__ import annotations

import datetime

import pytest


@pytest.mark.asyncio
async def test_insights_status_reports_selected_provider(client, seed_settings, auth_headers):
    resp = await client.get("/api/v1/insights/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "chatgpt"
    assert data["configured"] is False
    assert set(data["available_providers"]) == {"chatgpt", "claude", "grok"}


@pytest.mark.asyncio
async def test_insights_summary_requires_configuration(client, seed_settings, auth_headers):
    resp = await client.post("/api/v1/insights/summary", headers=auth_headers, json={})
    assert resp.status_code == 409
    assert "Configure an API key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_insights_summary_returns_generated_payload(monkeypatch, client, seed_settings, auth_headers):
    async def fake_generate(_db, *, question):
        from app.schemas.insight import InsightEvidenceMetric, InsightItem, InsightSummaryResponse

        return InsightSummaryResponse(
            provider="chatgpt",
            model="gpt-4.1-mini",
            generated_at=datetime.datetime(2026, 4, 13, 12, 0, tzinfo=datetime.timezone.utc),
            title="Weekly business pulse",
            summary="Sales are healthy, but low stock needs attention.",
            question=question,
            recommendations=[
                InsightItem(
                    title="Restock your top seller",
                    detail="Desk Dragon stock is drifting toward its reorder point.",
                    priority="high",
                    evidence=["Low stock alerts", "Gross sales"],
                    recommended_action="Queue a replenishment run before the next event.",
                )
            ],
            risks=[],
            suggested_questions=["Which SKUs are draining margin?"],
            evidence_metrics=[InsightEvidenceMetric(key="gross_sales", label="Gross sales", value="$1200.00")],
        )

    monkeypatch.setattr("app.api.v1.endpoints.insights.generate_insight_summary", fake_generate)

    resp = await client.post(
        "/api/v1/insights/summary",
        headers=auth_headers,
        json={"question": "What needs attention before the craft fair?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Weekly business pulse"
    assert data["question"] == "What needs attention before the craft fair?"
    assert data["provider"] == "chatgpt"
