from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    total_jobs: int = Field(..., examples=[5])
    total_pieces: int = Field(..., examples=[31])
    total_revenue: float = Field(..., examples=[311.94])
    total_costs: float = Field(..., examples=[187.16])
    total_platform_fees: float = Field(..., examples=[31.88])
    total_net_profit: float = Field(..., examples=[92.89])
    avg_profit_per_piece: float = Field(..., examples=[3.00])
    avg_margin_pct: float = Field(..., examples=[29.78])
    top_material: str | None = Field(None, examples=["PLA"])


class RevenueDataPoint(BaseModel):
    date: str = Field(..., examples=["2026-02-27"])
    revenue: float = Field(..., examples=[177.19])


class MaterialUsageDataPoint(BaseModel):
    material: str = Field(..., examples=["PLA"])
    count: int = Field(..., examples=[4])


class ProfitMarginDataPoint(BaseModel):
    date: str = Field(..., examples=["2026-02-27"])
    job: str = Field(..., examples=["001"])
    product: str = Field(..., examples=["Phone Stand"])
    margin: float = Field(..., examples=[29.5])
