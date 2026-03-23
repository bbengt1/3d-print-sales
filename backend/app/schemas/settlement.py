from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SettlementLineCreate(BaseModel):
    sale_id: uuid.UUID | None = None
    line_type: str = Field("sale", pattern="^(sale|fee|adjustment|reserve|other)$")
    description: str = Field(..., min_length=1, max_length=255)
    amount: Decimal
    notes: str | None = None


class SettlementLineResponse(BaseModel):
    id: uuid.UUID
    settlement_id: uuid.UUID
    sale_id: uuid.UUID | None = None
    line_type: str
    description: str
    amount: Decimal
    notes: str | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class MarketplaceSettlementCreate(BaseModel):
    settlement_number: str = Field(..., min_length=1, max_length=60)
    channel_id: uuid.UUID
    period_start: datetime.date
    period_end: datetime.date
    payout_date: datetime.date
    gross_sales: Decimal = Field(0)
    marketplace_fees: Decimal = Field(0)
    adjustments: Decimal = Field(0)
    reserves_held: Decimal = Field(0)
    net_deposit: Decimal
    notes: str | None = None
    lines: list[SettlementLineCreate] = Field(default_factory=list)


class MarketplaceSettlementResponse(BaseModel):
    id: uuid.UUID
    settlement_number: str
    channel_id: uuid.UUID
    period_start: datetime.date
    period_end: datetime.date
    payout_date: datetime.date
    gross_sales: Decimal
    marketplace_fees: Decimal
    adjustments: Decimal
    reserves_held: Decimal
    net_deposit: Decimal
    expected_net: Decimal
    discrepancy_amount: Decimal
    notes: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    lines: list[SettlementLineResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SettlementReconciliationRow(BaseModel):
    settlement_id: uuid.UUID
    settlement_number: str
    channel_id: uuid.UUID
    period_start: datetime.date
    period_end: datetime.date
    payout_date: datetime.date
    gross_sales: Decimal
    marketplace_fees: Decimal
    adjustments: Decimal
    reserves_held: Decimal
    net_deposit: Decimal
    expected_net: Decimal
    discrepancy_amount: Decimal


class SettlementReconciliationSummary(BaseModel):
    rows: list[SettlementReconciliationRow]
    total_gross_sales: Decimal
    total_marketplace_fees: Decimal
    total_adjustments: Decimal
    total_reserves_held: Decimal
    total_net_deposit: Decimal
    total_expected_net: Decimal
    total_discrepancy: Decimal
