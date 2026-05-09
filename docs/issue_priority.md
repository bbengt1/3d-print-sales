# Issue Priority

> **Source of truth for which issue to pick up next.** Updated as issues land, dependencies shift, or scope changes. Cross-session readers (and future Claude sessions) should start here when asked "what's next."
>
> **Last reviewed:** 2026-05-10 (Tier 1 done; Tier 2 #240/#245/#246/#250 done; Tier 3 #241/#247/#248/#251/#252/#260/#261 done; Tier 4 #253/#254/#255/#258/#259/#262-kits/#263-delivery done)
>
> **How to use this doc:**
> - Tiers are ordered top-to-bottom — start with Tier 1 unless there's a specific business reason to jump.
> - Within a tier, the listed order is the suggested execution order, but parallel work is fine when issues don't share dependencies.
> - Each row notes hard/soft dependencies. **Hard** means the dependent issue cannot ship without the prerequisite. **Soft** means the dependent issue ships fine on its own but will integrate cleaner if the prerequisite is in first.
> - When an issue lands, move it under "Recently landed" with the merge commit and date so the trail is visible.

---

## Tier 1 — Foundations (highest leverage, do first)

These either unblock many other issues, fix a known production risk, or establish a pattern subsequent issues mirror.

| Order | Issue | Why first | Unblocks |
|---|---|---|---|
| ~~1~~ | ~~#243~~ — **landed 2026-05-09** (PR #269, squash `16fee04`). | Allocator + race fix shipped. | (was Soft dep for #242, #245, #246, #248, #251, #252, #261, #263) |
| 2 | [#244 — email send](https://github.com/bbengt1/3d-print-sales/issues/244) — **Phase 1 landed 2026-05-09** (PR #270, squash `ab48cac`). Phase 2 (WeasyPrint PDF, Resend transport+webhook, editable templates, at-rest password encryption, frontend send modal) deferred and tracked in `docs/email_send.md` + the issue comment thread. Treat #244 as the Phase 2 umbrella. | SMTP send works today. PDF/Resend/webhook still deferred soft prereqs for #247, #248, #250, #257, #261, #263 — those issues' templates already note the soft dep is fine to ship around. | Soft dep for #247, #248, #250, #257, #261, #263 |
| ~~3~~ | ~~#239~~ — **backend landed 2026-05-09** (PR #271, squash `c3d3a1d`). Phase 2 follow-ups in `docs/bank_reconciliation.md`. | Backend ready for #240/#246 to plug into. | (was Hard dep for #240, #241, #246) |
| ~~4~~ | ~~#238~~ — **backend landed 2026-05-09** (PR #273, squash `e62298b`). Phase 2 (frontend, auto-monthly cron, MACRS) in `docs/fixed_assets.md`. | Pattern set for #252 (intangibles). | |

---

## Tier 2 — High ROI (after foundations)

| Order | Issue | Why | Notes |
|---|---|---|---|
| ~~5~~ | ~~#245~~ — **Phase 1 landed 2026-05-09** (PR #274, squash `8d157f7`). Phase 2 (per-location decrement, sale fulfillment-from, soft-warn, frontend) in `docs/inventory_locations.md`. | Models ready; integration deferred. | |
| ~~6~~ | ~~#240~~ — **Phase 1 landed 2026-05-09** (PR #280, squash `2c2bd68`). Phase 2 (CSV mapping UI, QFX, create-from-line, frontend) in `docs/statement_import.md`. | Hooks ready for #241 to plug into. | |
| 7 | [#249 — reporting parity (AP aging, BS, CF, TB, R&P, AR refactor)](https://github.com/bbengt1/3d-print-sales/issues/249) | Closes the visible reporting gap. Step 0: verify-first audit. | Large but tractable. |
| 8 | [#242 — production orders + finished-good costing](https://github.com/bbengt1/3d-print-sales/issues/242) | Ties `Job` operational data to GL inventory layers and corrects sales-side COGS. | Soft deps on #243 (done), #245 (Phase 1 done). Risky COGS shift — tests mandatory. |
| ~~9~~ | ~~#250~~ — **Phase 1 landed 2026-05-09** (PR #276, squash `88b7af9`). Phase 2 (S3, email-attach hook, virus scan, frontend) in `docs/attachments.md`. | Storage volume on prod ready. | |

---

## Tier 3 — Substantial features

| Order | Issue | Why | Notes |
|---|---|---|---|
| 10 | [#248 — credit notes + debit notes](https://github.com/bbengt1/3d-print-sales/issues/248) | Formal customer/vendor return documents. Closes the AR/AP refund-document gap. | Soft deps on #243, #244, #245, #242. |
| ~~11~~ | ~~#246~~ — **landed 2026-05-09** (PR #275, squash `ac94091`). Phase 2: edit endpoint, multi-currency, auto-create from bank import (paired with #241), frontend. | Per-line `posted_on` added to journal_lines. | |
| ~~12~~ | ~~#241~~ — **Phase 1 landed 2026-05-09** (PR #281, squash `926e949`). Ignore-action only; create_receipt/create_payment deferred. | Auto-applies during import. | |
| ~~13~~ | ~~#247~~ — **landed 2026-05-09** (PR #277, squash `82db7d1`). Phase 2: auto-email integration with #244, frontend, n8n cron workflow JSON. | Cron entry point `/run-due` ready for n8n. | |
| 14 | [#261 — sales orders + purchase orders](https://github.com/bbengt1/3d-print-sales/issues/261) | Fills out the sales and purchase cycles with formal intermediate documents. Symmetric, big-but-tractable. | Soft deps on #243, #244. |
| 15 | [#260 — accounting foundations cluster](https://github.com/bbengt1/3d-print-sales/issues/260) | Recurring JEs + suspense clearing + starting balances + verify-and-document tasks for the §7 🔁 rows. | Best after Tier 1+2 so the verify pass has the new context. |
| 16 | [#263 — sales auxiliary (late fees, delivery notes, billable expenses, withholding)](https://github.com/bbengt1/3d-print-sales/issues/263) | Four small AR-side gaps as one polish pass. | Soft deps on #244 for delivery-note email. |

---

## Tier 4 — Lower-frequency value

| Order | Issue | Why later | Notes |
|---|---|---|---|
| 17 | [#258 — compound + reverse-charge tax codes](https://github.com/bbengt1/3d-print-sales/issues/258) | Only matters when the operator hits a multi-jurisdiction or B2B-intl. scenario. Defer until that's real. | Forward-compatible with the existing single-rate code paths. |
| 18 | [#255 — divisions + projects](https://github.com/bbengt1/3d-print-sales/issues/255) | Useful for segmentation reporting; not blocking anyone. | Adds optional FKs across many models. |
| ~~19~~ | ~~#251~~ — **landed 2026-05-09** (PR #278, squash `5e45ac2`). Phase 2: receipt attachments via #250, approval_request integration, reimburse-as-Bill, frontend. | New COA account 2300. | |
| ~~20~~ | ~~#252~~ — **landed 2026-05-09** (PR #279, squash `15cf9f1`). Symmetric mirror of #238. Phase 2: auto-monthly cron, frontend. | 5 new COA accounts. | |
| 21 | [#259 — budgets + budget vs. actual P&L](https://github.com/bbengt1/3d-print-sales/issues/259) | Strategic/planning tool; less urgent than transactional gaps. | Custom report builder explicitly deferred from this issue. |
| 22 | [#262 — inventory polish (kits, merge dupes, starting balances)](https://github.com/bbengt1/3d-print-sales/issues/262) | Three small items bundled. Useful as catalog grows. | Independent of most other tiers. |
| 23 | [#264 — cross-cutting consistency pass](https://github.com/bbengt1/3d-print-sales/issues/264) | Form templates + archive flag audit + search/sort UX + PDF parity. **Touches many files** — land near the end of the queue so it consolidates a stable surface. | Best after most other issues to avoid re-doing migrations. |
| 24 | [#253 — custom fields](https://github.com/bbengt1/3d-print-sales/issues/253) | Power-user feature; not blocking anyone. | JSONB-backed; many scopes. |
| 25 | [#254 — batch operations + CSV import](https://github.com/bbengt1/3d-print-sales/issues/254) | Operator power tool; useful but not transaction-critical. | Master-data scopes only — transactions deliberately excluded. |

---

## Tier 5 — Defer

| Issue | Why deferred |
|---|---|
| [#256 — multi-currency (Phase 1)](https://github.com/bbengt1/3d-print-sales/issues/256) | Only worth the surface change when international sales become a real volume. Phase 1 doesn't even cover FX revaluation; full multi-currency is a long road. |
| [#257 — customer portal (Phase 1)](https://github.com/bbengt1/3d-print-sales/issues/257) | Hard dep on #244, but more importantly **expands the public attack surface**. Don't ship until the customer-facing payoff is real. |

---

## Operations / pre-existing (parallel track to the Manager.io walk)

These issues pre-date the Manager.io gap analysis and don't fit the tier structure cleanly. Treat them as a separate queue prioritized by operational pain.

| Issue | Notes |
|---|---|
| [#127 — Epic: marketplace API integrations (Etsy, Amazon, eBay, TikTok)](https://github.com/bbengt1/3d-print-sales/issues/127) | **Largest single piece of remaining work.** Better to land Tier 1 + #245 + #249 first so the integrations have the right inventory-location and reporting plumbing to plug into. |
| [#135 — CI/CD: GitHub Actions for GKE deployment](https://github.com/bbengt1/3d-print-sales/issues/135) | Only relevant if moving off web01. Park unless there's a concrete migration plan. |
| [#229 — auto job creation from print auto-discovery](https://github.com/bbengt1/3d-print-sales/issues/229) | Operational quality-of-life. Standalone, no dependencies on the Manager.io tier. Can land any time. |
| [#230 — catalog loaded filament from jobs when missing from inventory](https://github.com/bbengt1/3d-print-sales/issues/230) | Small ops win. Standalone. |
| [#231 — color-blind-friendly light mode](https://github.com/bbengt1/3d-print-sales/issues/231) | UX polish. Pair with #264's cross-cutting pass if convenient. |

---

## Recently landed (last 30 days)

| Issue / PR | Merged | Notes |
|---|---|---|
| [#243](https://github.com/bbengt1/3d-print-sales/issues/243) — race-safe reference number allocator (PR #269) | 2026-05-09 | Squash `16fee04`. Closed #243. New `reference_sequences` table + service. Sales fully switched to allocator (closes the historical row-count race). Invoices and quotes gain optional auto-numbering. `agents.md` Known Risks updated. |
| [#244](https://github.com/bbengt1/3d-print-sales/issues/244) — email send Phase 1 (PR #270) | 2026-05-09 | Squash `ab48cac`. SMTP transport via stdlib `smtplib`, EmailDelivery audit table, send + history endpoints on invoice/quote, hard-coded HTML+text templates. Phase 2 (WeasyPrint PDF, Resend, webhook, editable templates, password encryption, frontend modal) deferred — issue left open as Phase 2 umbrella. |
| [#239](https://github.com/bbengt1/3d-print-sales/issues/239) — bank account typing + recon worksheet (PR #271) | 2026-05-09 | Squash `c3d3a1d`. Backend complete: Account.is_bank_account, JournalLine.cleared_status, BankReconciliation/Line models, full lifecycle service, /api/v1/banking endpoints, edit-lock guard. Frontend deferred (no banking UI exists yet). Phase 2 in `docs/bank_reconciliation.md`. |
| Deploy hardening (PR #272) | 2026-05-09 | Squash `f1b5095`. Canonical `scripts/deploy.sh` in repo runs `alembic upgrade head` automatically. Fixes a real incident from #271's deploy where pending migrations did not run. Host `deploy.sh` updated to delegate. |
| [#238](https://github.com/bbengt1/3d-print-sales/issues/238) — fixed asset register backend (PR #273) | 2026-05-09 | Squash `e62298b`. FixedAsset/DepreciationEntry models, SL+DDB schedule math, manual-post + dispose flow, 5 new system COA accounts, idempotent `seed_chart_of_accounts`, optional `printer.fixed_asset_id`. Frontend deferred. |
| [#245](https://github.com/bbengt1/3d-print-sales/issues/245) — inventory locations Phase 1 (PR #274) | 2026-05-09 | Squash `8d157f7`. Locations CRUD + transfer lifecycle (pending → in_transit → completed). No GL impact. Per-location qty decrement and sale fulfillment-from deferred. |
| [#246](https://github.com/bbengt1/3d-print-sales/issues/246) — inter-account transfers (PR #275) | 2026-05-09 | Squash `ac94091`. Always-posted JE with per-line `posted_on` (new column on `journal_lines`). Edit-lock via #239 guard. |
| [#250](https://github.com/bbengt1/3d-print-sales/issues/250) — attachments Phase 1 (PR #276) | 2026-05-09 | Squash `88b7af9`. Polymorphic `(scope, record_id)` upload with magic-byte sniffing, Pillow webp thumbnails, soft delete, 100 MB/record cap. New `attachments_data` compose volume. Frontend + email-attach hook + S3 deferred. |
| [#247](https://github.com/bbengt1/3d-print-sales/issues/247) — recurring sales invoices (PR #277) | 2026-05-09 | Squash `82db7d1`. Cron-driven `/run-due`, snapshot pricing, future-only template propagation, failure-no-advance, auto-deactivate on `end_on`. |
| [#251](https://github.com/bbengt1/3d-print-sales/issues/251) — expense claims (PR #278) | 2026-05-09 | Squash `5e45ac2`. draft → submitted → approved → reimbursed lifecycle with JE postings + auto-reversal on cancel. New COA `2300` Owner Reimbursable Liability. |
| [#252](https://github.com/bbengt1/3d-print-sales/issues/252) — intangible assets + amortization (PR #279) | 2026-05-09 | Squash `15cf9f1`. Symmetric mirror of #238. SL+DDB math, dispose flow, 5 new COA accounts (1800/1850/6750/4920/6760). |
| [#240](https://github.com/bbengt1/3d-print-sales/issues/240) — statement import Phase 1 (PR #280) | 2026-05-09 | Squash `2c2bd68`. OFX (regex parser, no new dep) + CSV import; fitid dedup; manual match promotes JL to cleared via #239. |
| [#241](https://github.com/bbengt1/3d-print-sales/issues/241) — auto-match rules Phase 1 (PR #281) | 2026-05-09 | Squash `926e949`. Rules CRUD + auto-apply during import for the `ignore` action. create_receipt/create_payment deferred. |
| [#260](https://github.com/bbengt1/3d-print-sales/issues/260) — accounting foundations cluster (PR #282) | 2026-05-10 | Squash `83ba1d0`. Recurring JEs (mirror of #247), suspense report, starting-balances workflow. 2 new system COA accounts (1900, 3300). |
| [#258](https://github.com/bbengt1/3d-print-sales/issues/258) — compound + reverse-charge tax (PR #283) | 2026-05-10 | Squash `3dbac39`. is_compound + is_reverse_charge flags; TaxProfileComponent table; compute_for_line service. |
| [#255](https://github.com/bbengt1/3d-print-sales/issues/255) — divisions + projects Phase 1 (PR #284) | 2026-05-10 | Squash `1684219`. Master-data CRUD only; cross-table FKs deferred to Phase 2. |
| [#259](https://github.com/bbengt1/3d-print-sales/issues/259) — budgets Phase 1 (PR #285) | 2026-05-10 | Squash `6c47afe`. AccountBudget table + upsert/copy/delete. P&L integration deferred. |
| [#253](https://github.com/bbengt1/3d-print-sales/issues/253) — custom fields Phase 1 (PR #286) | 2026-05-10 | Squash `86418bd`. Side-table storage avoids touching every record schema. 6 field types, validation, soft-deactivate. |
| [#254](https://github.com/bbengt1/3d-print-sales/issues/254) — batch ops Phase 1 (PR #287) | 2026-05-10 | Squash `93d41ab`. Batch deactivate/activate/delete on master scopes (vendor/product/supply/customer/material). CSV import deferred. |
| [#262](https://github.com/bbengt1/3d-print-sales/issues/262) — inventory kits Phase 1 (PR #288) | 2026-05-10 | Squash `a79e6c9`. KitComponent model + define/replace/list. Sale-time explosion + find-and-merge + starting-balances import deferred. |
| [#248](https://github.com/bbengt1/3d-print-sales/issues/248) — credit + debit notes Phase 1 (PR #289) | 2026-05-10 | Squash `6cb0cb7`. Numbered notes with line items, JE on issue, apply-to-invoice/bill, void. 2 new COA accounts (4800 Sales Returns, 5400 Purchase Returns). Restock + email + frontend deferred. |
| [#261](https://github.com/bbengt1/3d-print-sales/issues/261) — sales + purchase orders Phase 1 (PR #290) | 2026-05-10 | Squash `335c234`. Symmetric SO/PO with confirm + cancel. No conversion/fulfillment tracking yet. |
| [#263](https://github.com/bbengt1/3d-print-sales/issues/263) — delivery notes Phase 1 (PR #291) | 2026-05-10 | Squash `d7c8abf`. Delivery-note piece only. Late fees, billable expenses, withholding tax remain ❌ as deferred sub-features. |
| [#266 / #267 / #268](https://github.com/bbengt1/3d-print-sales/issues/265) — Dependabot remediation | 2026-05-09 | Closed #265. axios 1.15.2, vite 8.0.5, python-multipart 0.0.27, Pillow 12.2.0, pytest 9.0.3. Deployed to web01 (`33b4e3e`). |

---

## Maintenance

- **When opening a new issue:** add it to the appropriate tier here in the same PR that opens the issue.
- **When closing an issue:** move it to "Recently landed" with the squash/merge commit and date.
- **When dependencies shift:** the soft/hard dep notes are the source of truth — update them so the tier ordering stays correct.
- **When a tier becomes empty:** promote the next tier's contents up. Don't let stale ordering linger.
- **Rough review cadence:** every ~30 days, or whenever a Tier 1 item lands. Update the "Last reviewed" date at the top.
