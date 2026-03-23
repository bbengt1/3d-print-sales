from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class StatementLine(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    amount: Decimal


class BalanceSheetSection(BaseModel):
    lines: list[StatementLine]
    total: Decimal


class BalanceSheetResponse(BaseModel):
    as_of_date: str
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection
    liabilities_and_equity_total: Decimal
    is_balanced: bool


class CashFlowSection(BaseModel):
    total: Decimal


class CashFlowSummaryResponse(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    operating: CashFlowSection
    investing: CashFlowSection
    financing: CashFlowSection
    net_change_in_cash: Decimal


class ProfitAndLossSection(BaseModel):
    lines: list[StatementLine]
    total: Decimal


class ProfitAndLossResponse(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    basis: str
    revenue: ProfitAndLossSection
    cogs: ProfitAndLossSection
    expenses: ProfitAndLossSection
    gross_profit: Decimal
    net_income: Decimal
