# Manager.io Feature Gap Analysis

> **Source:** [manager.io/guides](https://www.manager.io/guides) (full chapter index, fetched 2026-05-09).
> **Purpose:** Identify accounting / business-management features in Manager.io that are missing or under-developed in this 3D Print Sales app, and where existing features should be hardened or extended.
> **Non-goal:** Cloning Manager.io. We pull only what fits a 3D-print maker / marketplace seller. Payroll, investments, intangible asset amortization, sole-trader capital accounts, customer portals, etc. are intentionally deprioritized.
>
> **Status legend:**
> - ✅ Implemented — comparable feature exists.
> - 🔁 Partial / Needs hardening — exists but has gaps vs. Manager.io.
> - ❌ Missing — no equivalent today; candidate for new issue.
> - 🚫 Out of scope — listed in Manager.io but not relevant to this business.
>
> **Issue column:** to be filled in once GitHub issues are created/cross-referenced.

---

## 1. Bank, Cash & Reconciliation

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Bank & cash accounts (typed, vs. generic GL accounts) | ❌ | We have `account.py` (generic chart of accounts) but no first-class bank/cash account type with cleared/pending balance separation. | [#239](https://github.com/bbengt1/3d-print-sales/issues/239) |
| Bank statement import (CSV / OFX / QFX) | ❌ | OFX first, CSV second; QFX/QIF deferred. | [#240](https://github.com/bbengt1/3d-print-sales/issues/240) |
| Bank reconciliation workflow | ❌ | Hard-block on edits to reconciled lines; period-lock honored. | [#239](https://github.com/bbengt1/3d-print-sales/issues/239) |
| Receipt / payment rules (auto-categorize imported lines) | ❌ | Contains + regex rules with priority and dry-run. | [#241](https://github.com/bbengt1/3d-print-sales/issues/241) |
| Inter-account transfers | ❌ | Always-posted with separate per-line dates; depends on #239. | [#246](https://github.com/bbengt1/3d-print-sales/issues/246) |
| Credit-card account handling | ❌ | Covered as `bank_account_kind=credit_card` in #239. | [#239](https://github.com/bbengt1/3d-print-sales/issues/239) |
| Cleared vs. pending status on transactions | ❌ | `journal_line.cleared_status` enum added in #239. | [#239](https://github.com/bbengt1/3d-print-sales/issues/239) |

**3D-print relevance:** High. Operators reconcile Stripe / marketplace payouts / business checking weekly; today this is largely off-app.

---

## 2. Sales Cycle (Quote → Order → Invoice → Receipt)

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Sales quotes | ✅ | `quote.py` + quotes workflow doc. | |
| Sales orders (between quote and invoice) | ❌ | Optional intermediate document with partial fulfillment; symmetric with PO. | [#261](https://github.com/bbengt1/3d-print-sales/issues/261) |
| Sales invoices | ✅ | `invoice.py`, lifecycle doc. | |
| Recurring sales invoices | ❌ | External n8n cron, snapshot pricing, future-only template changes, auto-email toggle wired to #244. | [#247](https://github.com/bbengt1/3d-print-sales/issues/247) |
| Credit notes (formal document, not just a credit) | 🔁 | Numbered customer-facing document with line items, restock interaction with #242/#245, refund-in-cash, email via #244. | [#248](https://github.com/bbengt1/3d-print-sales/issues/248) |
| Late payment fees | ❌ | Per-customer rate + grace days; cron-driven via n8n. | [#263](https://github.com/bbengt1/3d-print-sales/issues/263) |
| Delivery notes (separate from invoice) | 🔁 | Numbered `DeliveryNote` derived from invoice; partial dispatch; email via #244. | [#263](https://github.com/bbengt1/3d-print-sales/issues/263) |
| Billable time | 🚫 | Not relevant — we don't bill labor hours. | |
| Billable expenses (pass-through) | ❌ | Bill-line → customer pass-through with optional markup. | [#263](https://github.com/bbengt1/3d-print-sales/issues/263) |
| Withholding tax on customer receipts | 🔁 | Generalize marketplace pattern via `WithholdingProfile` on customer. | [#263](https://github.com/bbengt1/3d-print-sales/issues/263) |
| Customer portal (self-service order/invoice view) | ❌ | Phase 1: read-only invoices/quotes/credit-notes/receipts via magic-link auth. | [#257](https://github.com/bbengt1/3d-print-sales/issues/257) |
| Email transactions (invoice/quote send + templates + tracking) | ❌ | Resend default + SMTP fallback; WeasyPrint PDF; opens tracking; synchronous send v1. | [#244](https://github.com/bbengt1/3d-print-sales/issues/244) |

---

## 3. Purchasing & AP

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Suppliers / vendors | ✅ | `vendor.py`. | |
| Purchase invoices (bills) | ✅ | `bill.py`, `bill_payment.py`. | |
| Purchase orders | ❌ | Optional intermediate document with partial fulfillment; symmetric with SO. | [#261](https://github.com/bbengt1/3d-print-sales/issues/261) |
| Purchase quotes / RFQs | ❌ | Out of scope per #261. | |
| Recurring purchase invoices | ✅ | `recurring_expense.py`. | |
| Debit notes (returns to vendors) | ❌ | Symmetric mirror of credit notes against vendors/bills. | [#248](https://github.com/bbengt1/3d-print-sales/issues/248) |
| Goods receipts | 🔁 | `material_receipt.py` gains optional `purchase_order_line_id` link via #261. | [#261](https://github.com/bbengt1/3d-print-sales/issues/261) |
| Freight-in on bills | ❌ | Handled as PO/bill line item in #261; no special model. | [#261](https://github.com/bbengt1/3d-print-sales/issues/261) |

---

## 4. Inventory & Production

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Inventory items | ✅ | `material.py`, `supply.py`, `product.py`. | |
| Bills of materials | ✅ | `product_bom_item.py`, BOM tracking doc. | |
| Inventory kits (saleable bundles) | ❌ | New `Product.kind=kit` with explode-on-sale; distinct from BOM. | [#262](https://github.com/bbengt1/3d-print-sales/issues/262) |
| Inventory locations (multi-location) | ❌ | Single→multi migration with Default location; UI auto-hides when only one location. | [#245](https://github.com/bbengt1/3d-print-sales/issues/245) |
| Inventory transfers between locations | ❌ | Hold model for in-transit; no GL impact. | [#245](https://github.com/bbengt1/3d-print-sales/issues/245) |
| Inventory adjustments (write-on / write-off, reasoned) | 🔁 | `inventory_transaction.py` supports adjustments; reason codes / approval flow appears thin (compare to `scrap_and_waste_workflows.md`). | |
| Production orders (BOM consumption + finished-good output) | 🔁 | New `ProductionOrder` entity with optional `Job` link; FIFO consumption + flat-rate overhead; sales-side COGS guard included. | [#242](https://github.com/bbengt1/3d-print-sales/issues/242) |
| Find-and-merge duplicate items | ❌ | Manual select + preview-and-confirm rewrite of FK references. | [#262](https://github.com/bbengt1/3d-print-sales/issues/262) |
| Inventory starting balances import | ❌ | CSV upload posts consolidated transactions per row. | [#262](https://github.com/bbengt1/3d-print-sales/issues/262) |

**3D-print relevance:** Production orders + locations are arguably the highest-value item in this section — tying a completed `Job` to inventory in/out at proper cost would close the books on every print.

---

## 5. Tax

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Tax codes (single-rate) | ✅ | `tax_profile.py`. | |
| Multi-component / compound tax codes (state + city, GST + PST) | 🔁 | New `TaxProfileComponent` table; sequential layer math; remittance breakdown. | [#258](https://github.com/bbengt1/3d-print-sales/issues/258) |
| Tax-inclusive vs. tax-exclusive entry per line | 🔁 | Worth auditing in invoice/quote forms. | |
| Reverse-charge VAT | ❌ | `is_reverse_charge` flag with paired payable/receivable lines. | [#258](https://github.com/bbengt1/3d-print-sales/issues/258) |
| Tax remittance tracking | ✅ | `tax_remittance.py`. | |

---

## 6. Fixed Assets — **High value gap**

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Fixed asset register | ❌ | Printers, cameras, computers are operationally tracked but not as depreciable capital assets. No book value, no acquisition cost on the GL. | [#238](https://github.com/bbengt1/3d-print-sales/issues/238) |
| Depreciation entries (manual + auto schedule) | ❌ | No depreciation schedules, no monthly journal automation. v1 covers manual posting; auto-scheduler deferred. | [#238](https://github.com/bbengt1/3d-print-sales/issues/238) |
| Asset disposal & gain/loss posting | ❌ | When a printer is sold/scrapped there's no clean accounting path. | [#238](https://github.com/bbengt1/3d-print-sales/issues/238) |
| Migration of fixed assets from prior system | ❌ | Greenfield only. Deferred from #238. | |

**3D-print relevance:** Very high. Printers are the largest line on the balance sheet for many shops. Closing this gap improves tax filings and gives real ROI per printer when combined with `printer_history`.

---

## 7. Accounting Foundations

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Chart of accounts | ✅ | `account.py`, starter COA doc. | |
| Account codes / display toggle | 🔁 | Verify-and-document task in #260. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Custom control accounts (group rollups) | 🔁 | Verify-and-document task in #260. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Special accounts (subledger style) | 🔁 | Verify-and-document task in #260. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Journal entries | ✅ | `journal_entry.py`, `journal_line.py`. | |
| Recurring journal entries | ❌ | n8n cron-driven, mirrors #247 pattern. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Period close / lock dates | 🔁 | Verify lock-date enforcement; small fixes in same PR. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Suspense / unbalanced clearing | ❌ | Seeded *Suspense* account + drill-down report. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Starting balances workflow (one-shot migration) | ❌ | Admin-only setup wizard posts a single migration JE. | [#260](https://github.com/bbengt1/3d-print-sales/issues/260) |
| Capital accounts / owner equity sub-accounts | 🚫 | Out of scope unless we add multi-owner LLC reporting. | |

---

## 8. Reporting

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| P&L | ✅ | `PLReportPage`, `report_service.py`. | |
| Balance sheet | 🔁 | Verify-first; add frontend page; period comparison. | [#249](https://github.com/bbengt1/3d-print-sales/issues/249) |
| Cash flow statement | 🔁 | Indirect method; verify-first; cash invariant test against Balance Sheet. | [#249](https://github.com/bbengt1/3d-print-sales/issues/249) |
| Trial balance | 🔁 | Verify-first; add frontend page; balance invariant test. | [#249](https://github.com/bbengt1/3d-print-sales/issues/249) |
| Sales / inventory reports | ✅ | Dedicated pages. | |
| Receipts & payments summary | ❌ | Categorized cash-movement view grouped by GL account with bank-line drill-down. | [#249](https://github.com/bbengt1/3d-print-sales/issues/249) |
| Aged receivables / payables | 🔁 | Shared `aging_service.py`; AP aging mirrors AR; AR refactored onto shared service. | [#249](https://github.com/bbengt1/3d-print-sales/issues/249) |
| Custom report builder (user-defined) | ❌ | Explicitly deferred from #259 — pending future scoping conversation. | |
| Forecasts / budgets | ❌ | Per-account monthly budgets + budget column on P&L. Forecasts deferred. | [#259](https://github.com/bbengt1/3d-print-sales/issues/259) |
| Sales invoice totals report | 🔁 | Sales report exists; check parity. | |

---

## 9. Cross-Cutting / Program Features

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Custom fields on records | ❌ | Per-scope JSONB column with definition table; admin CRUD; reportable. | [#253](https://github.com/bbengt1/3d-print-sales/issues/253) |
| Attachments on transactions | ❌ | Local FS behind storage abstraction; image thumbnails; soft delete; opt-in email attach via #244. | [#250](https://github.com/bbengt1/3d-print-sales/issues/250) |
| Batch create / update / delete | ❌ | Master-data scopes only (customers/vendors/products/materials/supplies); CSV import included. | [#254](https://github.com/bbengt1/3d-print-sales/issues/254) |
| Form defaults / templates | 🔁 | Per-form template system extending `settings_defaults.py`. | [#264](https://github.com/bbengt1/3d-print-sales/issues/264) |
| Divisions (cost-center reporting) | ❌ | Optional FK on bills/invoices/sales/JE; report filters on P&L/BS/CF. | [#255](https://github.com/bbengt1/3d-print-sales/issues/255) |
| Projects (cross-transaction tagging) | 🔁 | New `Project` entity separate from `Job`; optional FK across transactions. | [#255](https://github.com/bbengt1/3d-print-sales/issues/255) |
| Reference number sequencing (race-safe) | 🔁 | Central allocator with per-scope formats; closes existing `sale_number` race; adds optional auto-numbering for invoices/quotes. | [#243](https://github.com/bbengt1/3d-print-sales/issues/243) |
| Multi-currency support | ❌ | Phase 1: foreign-denominated docs with manual rates; revaluation deferred to Phase 2. | [#256](https://github.com/bbengt1/3d-print-sales/issues/256) |
| Inactive / archived flags across master data | 🔁 | Standardized `archived_at` timestamp pattern across all master data. | [#264](https://github.com/bbengt1/3d-print-sales/issues/264) |
| Search-records & sort-lists consistency | 🔁 | Shared list-query helper + `useListQuery` frontend hook. | [#264](https://github.com/bbengt1/3d-print-sales/issues/264) |
| PDF generation for forms | 🔁 | WeasyPrint parity audit; one shared scaffold across all printable docs. | [#264](https://github.com/bbengt1/3d-print-sales/issues/264) |
| Email send + tracking | ❌ | See §2. | [#244](https://github.com/bbengt1/3d-print-sales/issues/244) |
| History / audit trail | ✅ | `audit_log.py`, `finance_audit_log.md`. | |

---

## 10. Expense Claims

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Expense-claim payers (owner / employee / contractor) | ❌ | `payer_kind` enum; v1 covers owner; employee/contractor expansion non-breaking. | [#251](https://github.com/bbengt1/3d-print-sales/issues/251) |
| Expense claim entry (receipt → reimbursable liability) | ❌ | New `ExpenseClaim` document; JE posts on approve. | [#251](https://github.com/bbengt1/3d-print-sales/issues/251) |
| Reimbursement workflow (claim → approve → pay) | ❌ | Reuses `approval_request.py`; reimburse creates a Bill. | [#251](https://github.com/bbengt1/3d-print-sales/issues/251) |
| Attach receipt image to claim | ❌ | Soft-depends on #250. | [#251](https://github.com/bbengt1/3d-print-sales/issues/251) |

**3D-print relevance:** Useful even for a solo operator — owner-paid filament / hardware purchases on a personal card are common and currently book-keeping-awkward.

---

## 11. Intangible Assets & Amortization

| Feature | Status | Gap / Notes | Issue |
|---|---|---|---|
| Intangible asset register | ❌ | Symmetric mirror of #238 against intangibles. | [#252](https://github.com/bbengt1/3d-print-sales/issues/252) |
| Amortization entries (manual + auto schedule) | ❌ | Manual posting in v1; SL + DDB. | [#252](https://github.com/bbengt1/3d-print-sales/issues/252) |
| Asset disposal / write-off posting | ❌ | Full retirement + sale flow with gain/loss. | [#252](https://github.com/bbengt1/3d-print-sales/issues/252) |
| Migration of intangible assets from prior system | ❌ | Deferred from #252. | |

**3D-print relevance:** Lower than fixed assets but real — annual CAD/slicer subscriptions and bulk STL/asset-pack purchases benefit from amortization rather than expensing in a single month.

---

## 12. Out of Scope (listed for completeness)

These Manager.io chapters are **intentionally not pursued** unless the business model changes:

- Employees / payroll / payslips
- Investments (marketable securities)
- Customer/supplier portals (revisit if we get >5 recurring B2B clients)
- Self-hosting onboarding (we run our own deploy)
- Multi-business switching (single-business app)

---

## Suggested Prioritization

**Tier 1 — high accounting value, business-critical**
1. Fixed asset register + depreciation (printers as capital).
2. Bank/cash account typing + statement import + reconciliation.
3. Production orders tying `Job` to BOM consumption and finished-good costing.
4. Race-safe reference numbering (closes existing known risk + matches Manager.io pattern).
5. Email send for invoices/quotes with PDF + delivery tracking.

**Tier 2 — meaningful workflow upgrades**
6. Inventory locations + transfers.
7. Inter-account transfers + receipt/payment rules.
8. Recurring sales invoices.
9. Formal credit notes / debit notes (returns docs).
10. Aged AP + Balance Sheet + Cash Flow report parity.
11. Attachments on transactions.

**Tier 3 — power-user / scale**
12. Expense claims (owner-paid reimbursable expenses).
13. Intangible asset register + amortization (CAD/slicer subscriptions, asset packs).
14. Custom fields.
15. Batch create/update/delete.
16. Divisions / project reporting dimension on non-job transactions.
17. Multi-currency.
18. Customer portal.
19. Compound / reverse-charge tax codes.
20. Custom report builder & budgets/forecasts.

---

## Next Step

Walk this list against open GitHub issues. For each ❌ / 🔁 row:
- If an issue already exists, fill in the **Issue** column.
- If not, decide whether to open one (tier order above suggests sequence).
- Mark anything we explicitly decline as 🚫 with a one-line reason inline.
