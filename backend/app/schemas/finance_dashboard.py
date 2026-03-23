from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class FinanceDashboardSummary(BaseModel):
    cash_on_hand: Decimal
    unpaid_invoices: Decimal
    unpaid_bills: Decimal
    current_month_net_income: Decimal
    inventory_asset_value: Decimal
    tax_payable: Decimal
    payouts_in_transit: Decimal
