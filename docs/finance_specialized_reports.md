# Finance Specialized Reports

This document describes the specialized finance-reporting foundation added for Phase 17.

## Current Reports

The app now exposes dedicated API reports for:
- A/R aging
- A/P aging
- tax liability summary
- inventory valuation
- COGS breakdown

## A/R Aging

Current behavior:
- reuses the invoice aging logic built in Phase 15
- groups unpaid invoice balances into:
  - current
  - 1-30
  - 31-60
  - 61-90
  - 90+

## A/P Aging

Current behavior:
- groups unpaid bill balances into:
  - current
  - 1-30
  - 31-60
  - 61-90
  - 90+

## Tax Liability Summary

Current behavior:
- summarizes by tax profile
- separates:
  - seller-collected tax
  - marketplace-facilitated tax
  - remitted tax
  - outstanding liability

## Inventory Valuation

Current behavior:
- values remaining material inventory from material receipts
- uses remaining quantity and landed cost per gram
- reports total remaining quantity and total inventory value

## COGS Breakdown

Current behavior:
- groups sold units by period, channel, and product description
- reports:
  - units sold
  - COGS
  - revenue

## Current Limitation

This slice establishes specialized finance report APIs, but it does not yet include the dedicated frontend report pages promised by the broader Phase 17 plan.

## Related Files

- `backend/app/api/v1/endpoints/reports.py`
- `backend/app/services/report_service.py`
- `backend/tests/test_api_finance_reports.py`
