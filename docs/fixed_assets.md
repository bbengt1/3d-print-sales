# Fixed Asset Register

Operators capitalize equipment (printers, cameras, computers, post-processing rigs) on the balance sheet, depreciate them on a chosen schedule, and dispose them with gain/loss accounting (#238).

## Concepts

- **FixedAsset** — one capital purchase. Carries `acquisition_cost`, `salvage_value`, `useful_life_months`, `depreciation_method` (`straight_line` or `declining_balance`), and three GL account FKs (asset, accumulated depreciation, depreciation expense). Optional `acquisition_bill_id` traces back to the AP bill that booked the purchase.
- **DepreciationEntry** — one month of depreciation, with the resulting `journal_entry_id`. Idempotent per `(fixed_asset_id, period_end)`.
- **Status** — `active` → `fully_depreciated` (auto when book reaches salvage) → optionally `disposed` (operator action).

## COA seed (5 new accounts)

Added to `STARTER_CHART_OF_ACCOUNTS` and the `20260509_04` migration; `seed_chart_of_accounts` is now idempotent and tops up missing codes on existing installations.

| Code | Name | Type |
|---|---|---|
| 1700 | Equipment | asset (debit-normal) |
| 1750 | Accumulated Depreciation — Equipment | asset contra (credit-normal) |
| 6700 | Depreciation Expense | expense |
| 4910 | Gain on Disposal of Equipment | revenue |
| 6710 | Loss on Disposal of Equipment | expense |

These are defaults; operators can pick alternative accounts per asset via the `*_account_id` fields on create.

## Math

**Straight-line.** Monthly amount = `(cost − salvage) / life_months`. The schedule is generated for the full useful life and the final month rounds to bring the schedule's sum to exactly `cost − salvage`.

**Declining-balance.** Monthly amount = `book_value_start_of_period × (rate / 12)`, where `rate` defaults to `2 / life_years` (DDB) when not explicitly set. The service switches to a straight-line floor over the remaining life when SL would yield a larger monthly amount, ensuring the asset reaches salvage by end of life. Final-period adjustment forces the schedule to sum to exactly `cost − salvage`.

## Posting (manual)

`POST /api/v1/fixed-assets/post-depreciation` body: `{ period_end, asset_ids? }`.

Per asset, the service walks the planned schedule and posts a JE for every period that:
- has not yet been posted (idempotent — re-running is a no-op for already-posted months);
- is on or before `period_end`;
- is not in a closed accounting period.

Each post is balanced: Dr Depreciation Expense / Cr Accumulated Depreciation. After posting, the asset auto-flips to `fully_depreciated` if book value ≤ salvage.

## Disposal

`POST /api/v1/fixed-assets/{id}/dispose` body: `{ disposed_on, proceeds?, proceeds_account_id? }`.

1. Posts pending depreciation through `disposed_on`.
2. Computes `book_value = cost − accumulated`.
3. Posts the disposal JE:
   - **Cr** Equipment for `cost`
   - **Dr** Accumulated Depreciation for the full balance
   - **Dr** Cash/AR (`proceeds_account_id`) for `proceeds` if > 0
   - Residual `delta = proceeds − book_value` posts as **Cr** Gain when positive, **Dr** Loss when negative; zero on `delta == 0`.
4. Sets status `disposed`, stamps `disposed_on`, links the JE.
5. If a Printer is linked via `Printer.fixed_asset_id`, marks the printer inactive (preserves `printer_history` rows).

## Edit lock

`acquisition_cost`, `salvage_value`, `useful_life_months`, `depreciation_method`, `declining_balance_rate` are immutable once any depreciation is posted. To change them: reverse the posted entries first.

## Linking to a Printer

`Printer.fixed_asset_id` is a nullable FK. Operators link existing printers manually from the printer detail page. No auto-seeding — capitalization is a deliberate accounting decision per asset.

## Phase 2 follow-ups

- Auto-scheduled monthly depreciation posting (cron via n8n, mirroring #247's pattern).
- Frontend `/finance/fixed-assets` route — list, detail, schedule, disposal modal. Currently API-only.
- Component depreciation (sub-asset of a printer like a hot-end).
- Asset categories with shared default policies.
- Bulk import from prior accounting system.
- Tax-method depreciation (MACRS) parallel to book depreciation.
- Linking cameras / non-printer devices to fixed assets in the UI (model is already generic; only Printer has the FK today).
