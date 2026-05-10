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


class ProfitAndLossComparisonResponse(BaseModel):
    """#322 P2: side-by-side current vs prior-period P&L."""

    current: ProfitAndLossResponse
    prior: ProfitAndLossResponse
    deltas: dict[str, Decimal]


class JournalLineDrillRow(BaseModel):
    """#322 P2: one source journal line behind a report cell."""

    journal_entry_id: str
    entry_number: str
    entry_date: str
    line_id: str
    account_id: str
    account_code: str
    account_name: str
    entry_type: str
    amount: Decimal
    description: str | None = None
    source_type: str | None = None
    source_id: str | None = None


class AccountDrillDownResponse(BaseModel):
    account_id: str
    account_code: str
    account_name: str
    date_from: str | None = None
    date_to: str | None = None
    rows: list[JournalLineDrillRow]
    total_debit: Decimal
    total_credit: Decimal
    net_change: Decimal
