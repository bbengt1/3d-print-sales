from __future__ import annotations

from pydantic import BaseModel, Field


class SettingResponse(BaseModel):
    key: str = Field(..., examples=["default_profit_margin_pct"])
    value: str = Field(..., examples=["40"])
    notes: str | None = Field(None, examples=["Target markup on total cost"])

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str = Field(..., min_length=1, max_length=255, examples=["40"])


class BulkSettingUpdate(BaseModel):
    settings: dict[str, str] = Field(
        ...,
        examples=[{"default_profit_margin_pct": "40", "platform_fee_pct": "9.5"}],
    )
