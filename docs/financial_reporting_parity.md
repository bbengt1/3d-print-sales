# Financial Reporting Parity (Phase 1)

#249. Audit-then-fill approach. Most of the financial-statement surface was already shipped via closed issue #37; this PR adds the two missing pieces and documents the full set so operators (and future Claude sessions) can find everything from one place.

## What was already there (verified)

| Endpoint | Service | Notes |
|---|---|---|
| `GET /api/v1/reports/pl` | `generate_pl_report` | Standard P&L. |
| `GET /api/v1/reports/pl-accrual` | `generate_accrual_pl_report` | Accrual-basis P&L. |
| `GET /api/v1/reports/pl-cash` | `generate_cash_pl_report` | Cash-basis P&L. |
| `GET /api/v1/reports/balance-sheet` | `generate_balance_sheet_report` | As-of-date balance sheet, balanced check. |
| `GET /api/v1/reports/cash-flow` | `generate_cash_flow_summary_report` | Indirect-style cash flow summary. |
| `GET /api/v1/reports/ar-aging` | `generate_ar_aging_report` | AR aging buckets (also exposed via invoices.py). |
| `GET /api/v1/reports/ap-aging` | `generate_ap_aging_report` | AP aging buckets. |
| `GET /api/v1/reports/sales` | `generate_sales_report` | Sales report. |
| `GET /api/v1/reports/inventory` | `generate_inventory_report` | Inventory report. |
| `GET /api/v1/reports/inventory-valuation` | `generate_inventory_valuation_report` | Inventory valuation summary. |
| `GET /api/v1/reports/cogs-breakdown` | `generate_cogs_breakdown_report` | COGS breakdown by period. |
| `GET /api/v1/reports/tax-liability` | `generate_tax_liability_summary_report` | Tax liability summary. |

## What this PR adds

| Endpoint | Service | Notes |
|---|---|---|
| `GET /api/v1/reports/trial-balance` | `generate_trial_balance_report` | Account-by-account debit/credit balances at a point in time. Includes `is_balanced` invariant. |
| `GET /api/v1/reports/trial-balance.csv` | (CSV export) | UTF-8 CSV. |
| `GET /api/v1/reports/receipts-payments-summary` | `generate_receipts_payments_summary_report` | Categorized cash-movement view grouped by GL account over the period. Each row carries `inflows`, `outflows`, `net`, `transaction_count`, sorted by absolute net. Marks `is_bank_account` for downstream drill-down. |
| `GET /api/v1/reports/receipts-payments-summary.csv` | (CSV export) | UTF-8 CSV. |

## Trial balance behavior

The trial balance assigns each account's balance to its natural side. A debit-normal account with a positive running balance lands in the Debit column; if the running balance is negative (overdraft / contra position), it lands in Credit instead. Same logic in reverse for credit-normal accounts. A balanced book makes `total_debit == total_credit`; the response includes `is_balanced` so callers can assert it.

## Receipts & Payments Summary

For each account that had any journal-line activity in the date range:
- `inflows` = sum of debit amounts
- `outflows` = sum of credit amounts
- `net` = inflows − outflows
- `transaction_count` = number of journal lines

Sort: by `abs(net)` desc — biggest movers first. The `is_bank_account` flag is exposed so a future drill-down view can default to bank accounts only.

## Phase 2 follow-ups

- **Period comparison** on P&L / Balance Sheet / Cash Flow (side-by-side current vs. prior-period). Endpoints accept the inputs already; we just need a comparison rendering on the response side.
- **AR-aging service consolidation**: AR aging today lives in two places (`/api/v1/reports/ar-aging` and the legacy invoice-side `/api/v1/invoices/.../aging-report`). Both work; consolidating onto one shared `aging_service.py` is a refactor rather than a feature.
- **Cash Flow ↔ Balance Sheet ending-cash invariant test** — confirm `ending_cash(period_end) - ending_cash(period_start) == cash_flow_net_change`.
- **Drill-down**: clicking an account row in Receipts & Payments Summary returns the underlying journal lines.
- **Frontend** pages for the new endpoints + period-comparison UI.
- **PDF export** via #244's WeasyPrint renderer.
