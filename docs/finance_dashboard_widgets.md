# Finance Dashboard Widgets

This document describes the finance dashboard widget foundation added for Phase 17.

## Current Finance Widgets

The dashboard now includes a finance section with widgets for:
- cash on hand
- unpaid invoices
- unpaid bills
- current month net income
- inventory asset value
- tax payable
- payouts in transit

## Data Sources

Current widget logic is derived from:
- posted journal balances for cash and tax payable
- invoice balances for unpaid invoices
- bill balances for unpaid bills
- current-month posted journal activity for net income
- material receipts for inventory asset value
- future-dated marketplace settlements for payouts in transit

## Current Limitation

This slice adds the finance dashboard summary and UI cards, but deeper drill-down charts and dedicated finance dashboard pages can still expand later.

## Related Files

- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/schemas/finance_dashboard.py`
- `frontend/src/pages/DashboardPage.tsx`
- `backend/tests/test_api_dashboard_finance.py`
