# Intangible Assets

Symmetric mirror of [docs/fixed_assets.md](fixed_assets.md) for intangibles — CAD/slicer subscriptions, asset packs, brand/domain purchases, multi-year listing fees. #252.

## What's the same

- **Models**: `IntangibleAsset` + `AmortizationEntry` mirror `FixedAsset` + `DepreciationEntry`.
- **Math**: identical SL and DDB schedule generation with SL crossover.
- **Posting**: idempotent through a chosen month-end via `POST /api/v1/intangible-assets/post-amortization`.
- **Disposal**: same flow — post pending, then Cr asset / Dr accumulated / Dr cash / gain-or-loss.
- **Edit-lock**: critical fields immutable after first amortization post.

## What's different

- **Field naming**: `amortization_method`, `amortization_expense_account_id`, `accumulated_amortization_account_id`. (FA uses `depreciation_*`.)
- **No printer link**: intangibles aren't equipment.
- **Account codes** (auto-seeded by migration `20260509_10`):
  - `1800` Intangible Assets
  - `1850` Accumulated Amortization
  - `6750` Amortization Expense
  - `4920` Gain on Disposal of Intangibles
  - `6760` Loss on Disposal of Intangibles

## API

`/api/v1/intangible-assets` mirrors `/api/v1/fixed-assets` exactly — `list`, `create`, detail (with schedule), `patch`, `post-amortization`, `dispose`, `delete`.

## Phase 2 follow-ups

- Auto-monthly cron (n8n) — same gap as #238's Phase 2.
- Frontend `/finance/intangible-assets` route.
- Bulk import from prior accounting system.
- Tax-method amortization parallel to book.
