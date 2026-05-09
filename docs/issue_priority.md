# Issue Priority

> **Source of truth for which issue to pick up next.** Updated as issues land, dependencies shift, or scope changes. Cross-session readers (and future Claude sessions) should start here when asked "what's next."
>
> **Last reviewed:** 2026-05-09
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
| 1 | [#243 — race-safe reference number allocator](https://github.com/bbengt1/3d-print-sales/issues/243) | Small in scope, fast to land, **closes the existing `sale_number` race called out in `agents.md` Known Risks**. Also adds optional auto-numbering for invoices/quotes so the upcoming email-send flow has predictable numbers. | Soft dep for #242, #245, #246, #248, #251, #252, #261, #263 |
| 2 | [#244 — email send for invoices/quotes](https://github.com/bbengt1/3d-print-sales/issues/244) | Adds the WeasyPrint PDF renderer (no PDF generation in the stack today) plus the Resend/SMTP transport layer. Both are reused by many later issues. Immediately useful even alone. | Soft dep for #247, #248, #250, #257, #261, #263 |
| 3 | [#239 — bank account typing + reconciliation worksheet](https://github.com/bbengt1/3d-print-sales/issues/239) | Establishes `is_bank_account` on accounts, the `cleared_status` vocabulary on journal lines, and the per-line date pattern reconciliation depends on. Direct payoff: accountant-grade bank reconciliation we don't have today. | **Hard** dep for #240, #241, #246 |
| 4 | [#238 — fixed asset register + depreciation](https://github.com/bbengt1/3d-print-sales/issues/238) | Printers are the largest line on the balance sheet for this business and currently invisible to the books. Establishes the depreciation/disposal pattern #252 mirrors for intangibles. | Sets pattern reused by #252 |

---

## Tier 2 — High ROI (after foundations)

| Order | Issue | Why | Notes |
|---|---|---|---|
| 5 | [#245 — inventory locations + transfers](https://github.com/bbengt1/3d-print-sales/issues/245) | Single-location inventory becomes multi-location with a Default migration. Powers correct stock decrement on marketplace fulfillment. Soft prerequisite for #242 (production-order fulfillment) and #248 (credit-note restock). | Backfill is the riskiest migration step; well documented in the issue. |
| 6 | [#240 — bank statement import (OFX → CSV)](https://github.com/bbengt1/3d-print-sales/issues/240) | Major bookkeeping time-saver once #239 lands. Hard depends on #239. | OFX-first per scoping. |
| 7 | [#249 — reporting parity (AP aging, BS, CF, TB, R&P, AR refactor)](https://github.com/bbengt1/3d-print-sales/issues/249) | Closes the visible reporting gap (financial statements not surfaced as frontend pages today). Step 0 of the issue is a verify-first audit of what already exists. | Touches a lot of report wiring; CSV export only in v1. |
| 8 | [#242 — production orders + finished-good costing](https://github.com/bbengt1/3d-print-sales/issues/242) | High value: ties `Job` operational data to GL inventory layers and corrects sales-side COGS. Riskier behavior shift on the COGS path — tests are mandatory. | Soft deps on #243, #245. Coordinates with #248 on layer restoration. |
| 9 | [#250 — attachments on transactions](https://github.com/bbengt1/3d-print-sales/issues/250) | Receipt PDFs on bills, reference photos on jobs. Quality-of-life win plus AP audit trail. Soft prereq for #251's claim receipts. | Adds a persistent host volume on web01. |

---

## Tier 3 — Substantial features

| Order | Issue | Why | Notes |
|---|---|---|---|
| 10 | [#248 — credit notes + debit notes](https://github.com/bbengt1/3d-print-sales/issues/248) | Formal customer/vendor return documents. Closes the AR/AP refund-document gap. | Soft deps on #243, #244, #245, #242. |
| 11 | [#246 — inter-account transfers](https://github.com/bbengt1/3d-print-sales/issues/246) | Small once #239 lands; meaningful improvement over manual JEs. | Hard dep on #239. |
| 12 | [#241 — statement-line auto-match rules](https://github.com/bbengt1/3d-print-sales/issues/241) | Power-user layer on top of #240 — collapses the per-line review burden. | Hard dep on #240. |
| 13 | [#247 — recurring sales invoices](https://github.com/bbengt1/3d-print-sales/issues/247) | Useful for retainers, subscriptions, consignment statements. n8n cron-driven. | Soft dep on #244 for auto-email. |
| 14 | [#261 — sales orders + purchase orders](https://github.com/bbengt1/3d-print-sales/issues/261) | Fills out the sales and purchase cycles with formal intermediate documents. Symmetric, big-but-tractable. | Soft deps on #243, #244. |
| 15 | [#260 — accounting foundations cluster](https://github.com/bbengt1/3d-print-sales/issues/260) | Recurring JEs + suspense clearing + starting balances + verify-and-document tasks for the §7 🔁 rows. | Best after Tier 1+2 so the verify pass has the new context. |
| 16 | [#263 — sales auxiliary (late fees, delivery notes, billable expenses, withholding)](https://github.com/bbengt1/3d-print-sales/issues/263) | Four small AR-side gaps as one polish pass. | Soft deps on #244 for delivery-note email. |

---

## Tier 4 — Lower-frequency value

| Order | Issue | Why later | Notes |
|---|---|---|---|
| 17 | [#258 — compound + reverse-charge tax codes](https://github.com/bbengt1/3d-print-sales/issues/258) | Only matters when the operator hits a multi-jurisdiction or B2B-intl. scenario. Defer until that's real. | Forward-compatible with the existing single-rate code paths. |
| 18 | [#255 — divisions + projects](https://github.com/bbengt1/3d-print-sales/issues/255) | Useful for segmentation reporting; not blocking anyone. | Adds optional FKs across many models. |
| 19 | [#251 — expense claims (owner reimbursable)](https://github.com/bbengt1/3d-print-sales/issues/251) | Real for solo operator but workaround (manual JE) exists. | Soft dep on #250 for receipt photos. |
| 20 | [#252 — intangible assets + amortization](https://github.com/bbengt1/3d-print-sales/issues/252) | Symmetric mirror of #238; lower business value than fixed assets. | Mirrors #238's design — easy after that lands. |
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
| [#266 / #267 / #268](https://github.com/bbengt1/3d-print-sales/issues/265) — Dependabot remediation | 2026-05-09 | Closed #265. axios 1.15.2, vite 8.0.5, python-multipart 0.0.27, Pillow 12.2.0, pytest 9.0.3. Deployed to web01 (`33b4e3e`). |

---

## Maintenance

- **When opening a new issue:** add it to the appropriate tier here in the same PR that opens the issue.
- **When closing an issue:** move it to "Recently landed" with the squash/merge commit and date.
- **When dependencies shift:** the soft/hard dep notes are the source of truth — update them so the tier ordering stays correct.
- **When a tier becomes empty:** promote the next tier's contents up. Don't let stale ordering linger.
- **Rough review cadence:** every ~30 days, or whenever a Tier 1 item lands. Update the "Last reviewed" date at the top.
