from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.material import Material
from app.models.printer import Printer
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.setting import Setting
from app.schemas.insight import (
    AIProvider,
    InsightEvidenceMetric,
    InsightItem,
    InsightStatusResponse,
    InsightSummaryResponse,
)

SUPPORTED_AI_PROVIDERS: list[AIProvider] = ["chatgpt", "claude", "grok"]
ATTENTION_PRINTER_STATUSES = {"paused", "maintenance", "offline", "error"}


class AIInsightConfigurationError(ValueError):
    """Raised when the configured provider is incomplete."""


class AIInsightProviderError(RuntimeError):
    """Raised when the upstream provider request fails."""


@dataclass
class ProviderConfig:
    provider: AIProvider
    model: str
    api_key: str


def _stringify(value: Decimal | float | int | str | None) -> str:
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        normalized = value.quantize(Decimal("0.01"))
        return f"{normalized}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise AIInsightProviderError("Provider returned a non-JSON response.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise AIInsightProviderError("Provider returned malformed JSON.") from exc


def _build_metrics(snapshot: dict) -> list[InsightEvidenceMetric]:
    return [
        InsightEvidenceMetric(key="total_jobs", label="Total jobs", value=str(snapshot["job_summary"]["total_jobs"])),
        InsightEvidenceMetric(key="total_revenue", label="Job revenue", value=f"${snapshot['job_summary']['total_revenue']:.2f}"),
        InsightEvidenceMetric(key="total_net_profit", label="Job net profit", value=f"${snapshot['job_summary']['total_net_profit']:.2f}"),
        InsightEvidenceMetric(key="sales_orders", label="Completed sales orders", value=str(snapshot["sales_summary"]["total_sales"])),
        InsightEvidenceMetric(key="sales_gross_sales", label="Gross sales", value=f"${snapshot['sales_summary']['gross_sales']:.2f}"),
        InsightEvidenceMetric(key="sales_contribution_margin", label="Contribution margin", value=f"${snapshot['sales_summary']['contribution_margin']:.2f}"),
        InsightEvidenceMetric(key="low_stock_alerts", label="Low stock alerts", value=str(snapshot["inventory_summary"]["alert_count"])),
        InsightEvidenceMetric(key="attention_printers", label="Printers needing attention", value=str(snapshot["printer_summary"]["attention_count"])),
        InsightEvidenceMetric(key="printing_printers", label="Printers currently printing", value=str(snapshot["printer_summary"]["printing_count"])),
    ]


def _default_model_for(provider: AIProvider) -> str:
    if provider == "chatgpt":
        return "gpt-4.1-mini"
    if provider == "claude":
        return "claude-3-5-sonnet-latest"
    return "grok-3-mini"


async def _get_settings_map(db: AsyncSession) -> dict[str, str]:
    rows = (await db.execute(select(Setting))).scalars().all()
    return {row.key: row.value for row in rows}


async def get_ai_status(db: AsyncSession) -> InsightStatusResponse:
    settings_map = await _get_settings_map(db)
    return _build_ai_status(settings_map)


def _build_ai_status(settings_map: dict[str, str]) -> InsightStatusResponse:
    raw_provider = (settings_map.get("ai_provider") or "chatgpt").strip().lower()
    provider: AIProvider = raw_provider if raw_provider in SUPPORTED_AI_PROVIDERS else "chatgpt"
    model = (settings_map.get(f"ai_{provider}_model") or _default_model_for(provider)).strip()
    api_key = (settings_map.get(f"ai_{provider}_api_key") or "").strip()
    return InsightStatusResponse(
        provider=provider,
        model=model,
        configured=bool(api_key and model),
        available_providers=SUPPORTED_AI_PROVIDERS,
        note="Insights are read-only suggestions grounded in app data. Operator approval is still required for any business action.",
    )


async def _get_provider_config(db: AsyncSession) -> ProviderConfig:
    settings_map = await _get_settings_map(db)
    status = _build_ai_status(settings_map)
    api_key = (settings_map.get(f"ai_{status.provider}_api_key") or "").strip()
    if not api_key:
        raise AIInsightConfigurationError(
            f"Configure an API key for the selected provider ({status.provider}) in Admin Settings before generating insights."
        )
    return ProviderConfig(provider=status.provider, model=status.model, api_key=api_key)


async def _build_snapshot(db: AsyncSession) -> dict:
    job_row = (
        await db.execute(
            select(
                func.count(Job.id),
                func.coalesce(func.sum(Job.total_revenue), 0),
                func.coalesce(func.sum(Job.net_profit), 0),
            ).where(Job.is_deleted == False)
        )
    ).one()

    sale_rows = (
        await db.execute(select(Sale).where(Sale.is_deleted == False))
    ).scalars().all()
    completed_sales = [sale for sale in sale_rows if sale.status not in ("cancelled", "refunded")]

    gross_sales = sum(float(sale.total) for sale in completed_sales)
    contribution_margin = sum(float(sale.net_revenue) for sale in completed_sales)
    shipping_costs = sum(float(sale.shipping_cost) for sale in completed_sales)
    platform_fees = sum(float(sale.platform_fees) for sale in completed_sales)

    top_products_rows = (
        await db.execute(
            select(
                SaleItem.description,
                func.sum(SaleItem.quantity).label("qty"),
                func.sum(SaleItem.line_total).label("revenue"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.is_deleted == False, Sale.status.not_in(["cancelled", "refunded"]))
            .group_by(SaleItem.description)
            .order_by(func.sum(SaleItem.line_total).desc())
            .limit(5)
        )
    ).all()

    low_stock_products = (
        await db.execute(
            select(Product.name, Product.stock_qty, Product.reorder_point)
            .where(Product.is_active == True, Product.stock_qty <= Product.reorder_point)
            .order_by(Product.stock_qty.asc(), Product.name.asc())
            .limit(5)
        )
    ).all()
    low_stock_materials = (
        await db.execute(
            select(Material.name, Material.brand, Material.spools_in_stock, Material.reorder_point)
            .where(Material.active == True, Material.spools_in_stock <= Material.reorder_point)
            .order_by(Material.spools_in_stock.asc(), Material.name.asc())
            .limit(5)
        )
    ).all()

    printer_rows = (
        await db.execute(
            select(Printer.name, Printer.status, Printer.monitor_status, Printer.monitor_progress_percent)
            .where(Printer.is_active == True)
        )
    ).all()
    attention_printers = [
        row for row in printer_rows if (row.monitor_status or row.status) in ATTENTION_PRINTER_STATUSES
    ]
    printing_printers = [
        row for row in printer_rows if (row.monitor_status or row.status) == "printing"
    ]

    return {
        "job_summary": {
            "total_jobs": int(job_row[0] or 0),
            "total_revenue": float(job_row[1] or 0),
            "total_net_profit": float(job_row[2] or 0),
        },
        "sales_summary": {
            "total_sales": len(completed_sales),
            "gross_sales": gross_sales,
            "contribution_margin": contribution_margin,
            "shipping_costs": shipping_costs,
            "platform_fees": platform_fees,
        },
        "inventory_summary": {
            "alert_count": len(low_stock_products) + len(low_stock_materials),
            "products": [
                {"name": row.name, "stock_qty": row.stock_qty, "reorder_point": row.reorder_point}
                for row in low_stock_products
            ],
            "materials": [
                {
                    "name": row.name,
                    "brand": row.brand,
                    "spools_in_stock": row.spools_in_stock,
                    "reorder_point": row.reorder_point,
                }
                for row in low_stock_materials
            ],
        },
        "printer_summary": {
            "total_active": len(printer_rows),
            "attention_count": len(attention_printers),
            "printing_count": len(printing_printers),
            "attention_printers": [
                {"name": row.name, "status": row.monitor_status or row.status}
                for row in attention_printers[:5]
            ],
        },
        "top_products": [
            {
                "description": row.description,
                "quantity": int(row.qty or 0),
                "revenue": float(row.revenue or 0),
            }
            for row in top_products_rows
        ],
    }


def _build_prompt(snapshot: dict, question: str | None) -> tuple[str, str]:
    system_prompt = (
        "You are a read-only business intelligence assistant for a 3D printing business. "
        "Return specific, grounded operational insight. Do not invent data. "
        "Respond with a single JSON object using this shape exactly: "
        "{\"title\": string, \"summary\": string, "
        "\"recommendations\": [{\"title\": string, \"detail\": string, \"priority\": \"high\"|\"medium\"|\"low\", "
        "\"evidence\": [string], \"recommended_action\": string}], "
        "\"risks\": [{\"title\": string, \"detail\": string, \"priority\": \"high\"|\"medium\"|\"low\", "
        "\"evidence\": [string], \"recommended_action\": string}], "
        "\"suggested_questions\": [string]}. "
        "Keep recommendations and risks to at most 3 each. Use evidence strings that point to the provided metrics or entities."
    )
    user_prompt = (
        "Analyze this business snapshot and produce explainable, operator-facing insights.\n\n"
        f"Operator question: {question or 'What needs attention right now, what should we print or restock next, and where is margin at risk?'}\n\n"
        f"Business snapshot JSON:\n{json.dumps(snapshot, indent=2)}"
    )
    return system_prompt, user_prompt


async def _request_openai_chat_completion(config: ProviderConfig, system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={
                "model": config.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
    if response.status_code >= 400:
        raise AIInsightProviderError(f"ChatGPT request failed with status {response.status_code}.")
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def _request_anthropic_message(config: ProviderConfig, system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": config.model,
                "max_tokens": 1200,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
    if response.status_code >= 400:
        raise AIInsightProviderError(f"Claude request failed with status {response.status_code}.")
    data = response.json()
    return "\n".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )


async def _request_xai_chat_completion(config: ProviderConfig, system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={
                "model": config.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
    if response.status_code >= 400:
        raise AIInsightProviderError(f"Grok request failed with status {response.status_code}.")
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def generate_insight_summary(db: AsyncSession, *, question: str | None) -> InsightSummaryResponse:
    config = await _get_provider_config(db)
    snapshot = await _build_snapshot(db)
    system_prompt, user_prompt = _build_prompt(snapshot, question)

    if config.provider == "chatgpt":
        raw_content = await _request_openai_chat_completion(config, system_prompt, user_prompt)
    elif config.provider == "claude":
        raw_content = await _request_anthropic_message(config, system_prompt, user_prompt)
    else:
        raw_content = await _request_xai_chat_completion(config, system_prompt, user_prompt)

    payload = _extract_json_object(raw_content)
    recommendations = [
        InsightItem(**item) for item in payload.get("recommendations", [])[:3]
    ]
    risks = [InsightItem(**item) for item in payload.get("risks", [])[:3]]

    return InsightSummaryResponse(
        provider=config.provider,
        model=config.model,
        generated_at=datetime.datetime.now(datetime.timezone.utc),
        title=payload.get("title") or "Business insight summary",
        summary=payload.get("summary") or "No summary returned by provider.",
        question=question,
        recommendations=recommendations,
        risks=risks,
        suggested_questions=payload.get("suggested_questions", [])[:3],
        evidence_metrics=_build_metrics(snapshot),
    )
