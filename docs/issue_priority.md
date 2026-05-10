# Issue Priority

> **Source of truth for which issue to pick up next.** Updated as issues land, dependencies shift, or scope changes. Cross-session readers (and future Claude sessions) should start here when asked "what's next."
>
> **Last reviewed:** 2026-05-10 (afternoon) — Manager.io gap walk substantively complete + 25 P1 follow-up fixes (#360–#384) landed. 5 trackers open; no Tier 1 / Tier 2 items remain. 60+ PRs landed since 2026-05-09.

---

## Open issues — current state

5 issues open as of 2026-05-10. All are Phase 2 trackers with the original Phase 1 already in production; the residual scope is meaningful but lower-leverage than what's already shipped. Recommended sequence is **#318 first** (the missing piece operators feel the moment they add a second location), the others as a "pick when relevant" backlog.

| # | What shipped | What's left | Next-pickup priority |
|---|---|---|---|
| **[#318](https://github.com/bbengt1/3d-print-sales/issues/318)** multi-location | `Sale.fulfillment_location_id` field, per-location stock snapshot, default-fulfillment-location admin endpoint (PR #340) | Per-location qty decrement on sale fulfillment, soft-warn-but-allow on negative projected stock, in-transit hold computation | **High** — needs a `ProductLocationStock` SoT model; biggest of the five. |
| **[#316](https://github.com/bbengt1/3d-print-sales/issues/316)** bank rules | `create_journal_entry` rule action, dry-run preview, create-rule-from-line, `category_account_id` + `counterparty_name` columns (PR #337) | `create_receipt` / `create_payment` / `create_inter_account_transfer` actions | Medium — the `create_journal_entry` action covers most categorize-and-post cases; these add nuance only when bank lines should flow into AR/AP rather than directly to a P&L category. |
| **[#326](https://github.com/bbengt1/3d-print-sales/issues/326)** custom fields | Hard-delete endpoint, value-search endpoint (PR #343) | Computed/formula fields (`days_open` style), multi-value (checkbox/tags), per-line custom fields | Medium — worth doing when you start authoring lots of custom fields. |
| **[#324](https://github.com/bbengt1/3d-print-sales/issues/324)** expense claims | Mileage line type with rate setting (PR #341); receipt attachments already work via existing `AttachmentsPanel` (scope=expense_claim) | Approval-request workflow integration, reimburse-as-Bill alternative path | Medium — approval workflow only useful when you have multiple users. |
| **[#321](https://github.com/bbengt1/3d-print-sales/issues/321)** returns | Refund-in-cash on credit notes, `credit_note` registered as EmailScope (PR #342) | Marketplace settlement bridging | Low — marketplace settlement was paired with #127 (closed); effectively defer indefinitely unless an Etsy/Amazon flow reactivates. |

**My take:** ship #318 next, leave the others as a known backlog. The current `/accounting` workspace + reporting suite + COGS FIFO covers the operational ground that mattered.

---

## Closed as won't-do

Reasons recorded on each issue. Reopen if the trigger condition fires.

| # | Why won't-do |
|---|---|
| ~~#127~~ Etsy/Amazon/eBay/TikTok epic | Multi-quarter epic with vendor-specific OAuth + contracts. Existing settlement-import flow handles the manual side. Reopen for one specific platform when there's a clear capacity-and-revenue case. |
| ~~#135~~ GKE CI/CD | web01 docker-compose deploy works and was hardened in PR #356. GKE only worth migrating to once you actually need multi-region or per-PR previews. |
| ~~#244~~ email Phase 2 (PDF + Resend) | SMTP path is sufficient. WeasyPrint, Resend, webhook delivery, at-rest password encryption all deferred indefinitely. |
| ~~#256~~ multi-currency Phase 1 | USD-only operations. Reopen if international expansion plans emerge. |
| ~~#257~~ customer portal | Public-internet attack surface; needs security review before code, plus a real customer-facing payoff (do customers actually want to log in vs. receive PDF emails?). |
| ~~#319~~ multi-currency Phase 2 | Same reason as #256. |
| ~~#323~~ attachments S3 + virus scan | Local disk works. Reopen if attachment volume or compliance requirements change. |
| ~~#329~~ tax reverse-charge JE legs | Reverse-charge only matters for cross-border B2B. US-only ops. Component breakdown + reverse-charge buckets already shipped in PR #336. |
| ~~#331~~ list/forms — archive uniformity + PDF parity | Form templates shipped. Archive uniformity is invasive across 20+ models with mixed flag conventions and hurts nobody operationally. PDF parity blocked on the killed #244 PDF stack. |

---

## Recently landed (2026-05-10)

PRs from today's session, in order. Total 17 today (12 features + 5 fixes/deploys).

| PR | Issue | What landed |
|---|---|---|
| [#332](https://github.com/bbengt1/3d-print-sales/pull/332) | #298–#313 | All 16 frontend Phase 1 surfaces — the full `/accounting` workspace |
| [#333](https://github.com/bbengt1/3d-print-sales/pull/333) | #314 | banking edit-lock coverage + period-close lock dates |
| [#334](https://github.com/bbengt1/3d-print-sales/pull/334) | #322 | reports — AR-aging consolidation, P&L period comparison, account drill-down |
| [#335](https://github.com/bbengt1/3d-print-sales/pull/335) | #330 | starting-balances CSV, suspense reclassify, n8n cron workflows |
| [#336](https://github.com/bbengt1/3d-print-sales/pull/336) | #329 | tax — component breakdown + reverse-charge tracking |
| [#337](https://github.com/bbengt1/3d-print-sales/pull/337) | #316 | bank-rule `create_journal_entry` action + dry-run + create-from-line |
| [#338](https://github.com/bbengt1/3d-print-sales/pull/338) | #325 | fixed assets — post-monthly-due cron + bulk CSV import |
| [#339](https://github.com/bbengt1/3d-print-sales/pull/339) | #320 | email — editable templates + Setting.value bumped to TEXT |
| [#340](https://github.com/bbengt1/3d-print-sales/pull/340) | #318 | multi-location — Sale.fulfillment_location_id + per-location snapshot |
| [#341](https://github.com/bbengt1/3d-print-sales/pull/341) | #324 | expense claims — mileage line type |
| [#342](https://github.com/bbengt1/3d-print-sales/pull/342) | #321 | returns — cash refund + credit_note email scope |
| [#343](https://github.com/bbengt1/3d-print-sales/pull/343) | #326 | custom fields — hard delete + value search |
| [#344](https://github.com/bbengt1/3d-print-sales/pull/344) | #327 | batch — master-data CSV import + undo + audit-log |
| [#345](https://github.com/bbengt1/3d-print-sales/pull/345) | #328 | divisions — division/project FKs across docs + P&L filter |
| [#346](https://github.com/bbengt1/3d-print-sales/pull/346) | #331 | forms — form-template CRUD |
| [#347](https://github.com/bbengt1/3d-print-sales/pull/347) | — | fix nav: wire Accounting workspace into top nav |
| [#348](https://github.com/bbengt1/3d-print-sales/pull/348) | #262 | inventory — starting-balances CSV import |
| [#349](https://github.com/bbengt1/3d-print-sales/pull/349) | #262 | inventory — find-and-merge materials/products |
| [#350](https://github.com/bbengt1/3d-print-sales/pull/350) | #263 | invoicing — late-payment-fee cron + per-customer override |
| [#351](https://github.com/bbengt1/3d-print-sales/pull/351) | #263 | AR — customer withholding tax |
| [#352](https://github.com/bbengt1/3d-print-sales/pull/352) | #263 | AR — billable expenses pass-through |
| [#353](https://github.com/bbengt1/3d-print-sales/pull/353) | #230 | materials — filament resolve-or-catalog from print metadata |
| [#354](https://github.com/bbengt1/3d-print-sales/pull/354) | — | fix(alembic): postgres-compatible boolean defaults |
| [#355](https://github.com/bbengt1/3d-print-sales/pull/355) | — | fix(alembic): drop duplicate column-then-explicit index |
| [#356](https://github.com/bbengt1/3d-print-sales/pull/356) | — | fix(deploy): run alembic before bringing backend up |
| [#357](https://github.com/bbengt1/3d-print-sales/pull/357) | #229 | jobs — auto-discovery from watch directories |
| [#358](https://github.com/bbengt1/3d-print-sales/pull/358) | #317 | COGS — sales-side FIFO rewrite (flag-gated, default off) |
| [#359](https://github.com/bbengt1/3d-print-sales/pull/359) | #315 + #327 | bank-import — QFX format, persisted CSV mapping, create-tx-from-line |
| [#379](https://github.com/bbengt1/3d-print-sales/pull/379) | #334 | P1 fix — drill-down missing account → 404 (Codex review) |
| [#380](https://github.com/bbengt1/3d-print-sales/pull/380) | #297 | P1 fix — reject unknown tax profile on invoice creation (Codex review) |
| [#381](https://github.com/bbengt1/3d-print-sales/pull/381) | #335 | P1 fix — validate `as_of` CSV date returns 4xx (Codex review) |
| [#382](https://github.com/bbengt1/3d-print-sales/pull/382) | #333 | P1 fix — map `JournalLineLockedError` to 409 on JE reverse (Codex review) |
| [#383](https://github.com/bbengt1/3d-print-sales/pull/383) | #292 | P1 fix — restrict receipts/payments summary to cash accounts (Codex review) |
| [#384](https://github.com/bbengt1/3d-print-sales/pull/384) | #295 | P1 fix — require auth on `/tax/compute` + JE reference_sequence backfill migration (Codex review) |

> **Doc gap note:** Earlier P1 follow-up fixes #360–#378 (afternoon batch — startup ORM register, banking integrity, intangibles, budgets, kits, etc.) landed but were not added to this table at the time. Recover from `git log --oneline b80bdbc..0283fb6` if a full reconstruction is needed.

---

## Recently landed (2026-05-09)

The original Manager.io gap walk landed across these PRs. Trimmed for brevity; full detail in the merge commits.

| Issue / PR | What |
|---|---|
| [#243](https://github.com/bbengt1/3d-print-sales/issues/243) (PR #269) | Race-safe reference number allocator |
| [#244](https://github.com/bbengt1/3d-print-sales/issues/244) (PR #270) | Email send Phase 1 (SMTP, EmailDelivery audit, send + history endpoints) |
| [#239](https://github.com/bbengt1/3d-print-sales/issues/239) (PR #271) | Bank account typing + reconciliation worksheet |
| Deploy hardening (PR #272) | First version of `scripts/deploy.sh` with auto-`alembic upgrade head` |
| [#238](https://github.com/bbengt1/3d-print-sales/issues/238) (PR #273) | Fixed asset register backend |
| [#245](https://github.com/bbengt1/3d-print-sales/issues/245) (PR #274) | Inventory locations Phase 1 |
| [#246](https://github.com/bbengt1/3d-print-sales/issues/246) (PR #275) | Inter-account transfers |
| [#250](https://github.com/bbengt1/3d-print-sales/issues/250) (PR #276) | Attachments Phase 1 |
| [#247](https://github.com/bbengt1/3d-print-sales/issues/247) (PR #277) | Recurring sales invoices |
| [#251](https://github.com/bbengt1/3d-print-sales/issues/251) (PR #278) | Expense claims |
| [#252](https://github.com/bbengt1/3d-print-sales/issues/252) (PR #279) | Intangible assets + amortization |
| [#240](https://github.com/bbengt1/3d-print-sales/issues/240) (PR #280) | Statement import Phase 1 |
| [#241](https://github.com/bbengt1/3d-print-sales/issues/241) (PR #281) | Auto-match rules Phase 1 |
| [#260](https://github.com/bbengt1/3d-print-sales/issues/260) (PR #282) | Accounting foundations cluster |
| [#258](https://github.com/bbengt1/3d-print-sales/issues/258) (PR #283) | Compound + reverse-charge tax |
| [#255](https://github.com/bbengt1/3d-print-sales/issues/255) (PR #284) | Divisions + projects Phase 1 |
| [#259](https://github.com/bbengt1/3d-print-sales/issues/259) (PR #285) | Budgets Phase 1 |
| [#253](https://github.com/bbengt1/3d-print-sales/issues/253) (PR #286) | Custom fields Phase 1 |
| [#254](https://github.com/bbengt1/3d-print-sales/issues/254) (PR #287) | Batch ops Phase 1 |
| [#262](https://github.com/bbengt1/3d-print-sales/issues/262) (PR #288) | Inventory kits Phase 1 |
| [#248](https://github.com/bbengt1/3d-print-sales/issues/248) (PR #289) | Credit + debit notes Phase 1 |
| [#261](https://github.com/bbengt1/3d-print-sales/issues/261) (PR #290) | Sales + purchase orders Phase 1 |
| [#263](https://github.com/bbengt1/3d-print-sales/issues/263) (PR #291) | Delivery notes Phase 1 |
| [#249](https://github.com/bbengt1/3d-print-sales/issues/249) (PR #292) | Reporting parity Phase 1 (Trial Balance + R&P Summary) |
| [#242](https://github.com/bbengt1/3d-print-sales/issues/242) (PR #293) | Production orders Phase 1 |
| [#264](https://github.com/bbengt1/3d-print-sales/issues/264) (PR #294) | Consistency-pass foundation (`list_query` helper) |
| Phase 2 batches (PRs #295/#296/#297) | First Phase 2 wave: tax compute endpoint, JE allocator migration, BS/CF invariant tests, recurring-invoice auto-email, SO/PO conversions, IAT edit endpoint, invoice tax_profile_id auto-compute |
| Dependabot remediation (#266/#267/#268) | axios 1.15.2, vite 8.0.5, python-multipart 0.0.27, Pillow 12.2.0, pytest 9.0.3 |

---

## Maintenance

- **When opening a new issue:** add it under "Open issues — current state" with what's expected to ship vs. what's deferred.
- **When closing an issue:** move it under "Recently landed" with the merge PR and date. Trim entries older than ~30 days.
- **When closing as won't-do:** add it under "Closed as won't-do" with the trigger condition that would justify reopening.
- **Rough review cadence:** every ~30 days, or whenever multiple issues land in a single session. Update the "Last reviewed" date at the top.
