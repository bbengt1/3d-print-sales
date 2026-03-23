# Formal Financial Statements

This document describes the formal financial statement foundation added for Phase 17.

## Current Statements

The app now exposes API support for:
- balance sheet
- cash flow summary
- accrual-basis P&L
- cash-basis P&L

## Balance Sheet

Current behavior:
- uses posted journal lines up to an `as_of_date`
- groups balances into:
  - assets
  - liabilities
  - equity
- reports whether the statement balances

## Accrual P&L

Current behavior:
- uses posted journal activity in the requested date range
- groups balances into:
  - revenue
  - COGS
  - expenses
- calculates gross profit and net income

## Cash-Basis P&L

Current behavior:
- uses paid amounts from invoices and bills as the current cash-basis simplification
- reports cash receipts as revenue and cash disbursements as expenses

## Cash Flow Summary

Current behavior:
- treats customer payment application as operating cash inflow
- treats bill payments as operating cash outflow
- reports operating / investing / financing sections
- investing and financing are currently zeroed placeholders pending deeper coverage

## Current Limitation

This slice establishes the API foundation for formal financial statements, but CSV export and dedicated frontend statement pages are still part of the broader remaining Phase 17 work.

## Related Files

- `backend/app/api/v1/endpoints/reports.py`
- `backend/app/services/report_service.py`
- `backend/app/schemas/statements.py`
- `backend/tests/test_api_statements.py`
