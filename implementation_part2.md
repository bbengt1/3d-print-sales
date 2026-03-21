# 3D Print Sales — Implementation Part 2

## Progress Log

### Phase 11 Completed
- [x] Issue #12 — Audit and rename ambiguous financial fields across backend and frontend
  - Added finance naming matrix doc: `docs/finance_metric_naming.md`
  - Renamed sales/reporting terminology across backend, frontend, tests, and docs
  - Updated README to reflect the new terminology
- [x] Issue #13 — Correct sales profitability metrics and expose layered profit views
  - Added explicit sales profit layers across API/reporting/UI:
    - `gross_sales`
    - `item_cogs`
    - `gross_profit`
    - `platform_fees`
    - `shipping_costs`
    - `contribution_margin`
  - Added sale-level `item_cogs` and `gross_profit` to detail responses
  - Expanded sales metrics and report summaries/channel breakdowns to include fee and shipping impact
  - Documented that `net_profit` is intentionally not exposed yet until overhead allocation exists
- [x] Issue #14 — Refactor P&L reporting to avoid double-counting and separate operational vs financial reporting
  - Refactored P&L so `total_revenue` is based on realized sales revenue only
  - Moved job-side `total_revenue` into `operational_production_estimate` for operational context
  - Updated P&L summary, period rows, CSV export, and frontend report page to reflect the new basis
  - Added reporting-basis documentation explaining why production estimates are excluded from financial revenue
  - Added/updated tests verifying realized sales revenue is no longer combined with production-side expected revenue
- [x] Issue #15 — Add finance glossary and metric definition documentation
  - Expanded `docs/finance_metric_naming.md` into a broader finance glossary
  - Documented revenue terms, cost terms, profit layers, jobs/calculator terms, inventory terms, tax terms, dashboard terms, and P&L reporting basis
  - Added plain-English definitions, current formulas/sources, and key cautions for exposed metrics
  - Updated README to point at the glossary as the canonical finance terminology reference

### In Progress
- [ ] Issue #16 — Accounting foundation and chart of accounts
  - Adding initial accounting-domain models: accounts, accounting periods, journal entries, journal lines
  - Adding starter chart of accounts seeding and balanced journal validation service
  - Adding backend foundation tests for seeding, period control, and balanced/unbalanced journal entries

### Maintenance Completed
- [x] Issue #44 — Fix backend test environment and API rate-limit failures in local/CI test runs
  - Added repo-level `.python-version` pinned to Python 3.13
  - Added `TESTING` config flag and disabled request rate limiting middleware during tests
  - Updated backend test bootstrap to set `TESTING=true`
  - Added `backend/pytest.ini` to make asyncio loop scope explicit
  - Updated README backend testing instructions and environment notes
- [x] Issue #45 — Fix frontend TypeScript configuration and path-alias build failures
  - Added TypeScript `baseUrl`/`paths` mapping for `@/*` in `frontend/tsconfig.app.json`
  - Resolved frontend build-blocking TypeScript issues after alias resolution (tooltip formatter typing, pie label typing, unused imports)
  - Verified `npm run build` now succeeds in a clean local frontend environment
  - Updated README with frontend build validation guidance

## Executive Summary

The current application is **well structured, modern, and genuinely useful operationally**. It already does several things very well:

- job costing
n- pricing guidance
- product and inventory tracking
- sales channel fee handling
- reporting/dashboard presentation
- clean navigation and page structure

That said, it is still closer to a **production + quoting + sales operations app** than a **true financial application**.

The main gap is that the system currently calculates financial-looking numbers, but it does **not yet model the accounting reality of the business**:

- no chart of accounts
- no general ledger / journal entries
- no accounts receivable or payable
- no expense/vendor management
- no payout settlement tracking
- no real COGS recognition workflow
- no cash vs accrual reporting separation
- no tax liability tracking
- no reconciliation workflows
- no audit trail for finance-sensitive changes

## Overall Review

## What is already strong

1. **Architecture is good**
   - Backend is cleanly separated into models, schemas, services, and API endpoints.
   - Frontend is organized by page/domain and easy to extend.
   - The repo is in a good place for a second implementation phase rather than a rewrite.

2. **The app already understands the 3D printing business domain**
   - material cost per gram
   - machine time
   - labor and design time
   - packaging/shipping
   - platform fees
   - stock movement for finished products

3. **The UI/layout is not the problem**
   - The navigation and page organization are logical.
   - Reports/dashboard pages are clean and readable.
   - This is a strong base to keep and deepen.

## Main issue

The app currently answers:
- “What should I charge?”
- “What did this job cost?”
- “How much stock do I have?”

But it does **not fully answer**:
- “Did I actually make money this month?”
- “What is my true COGS vs inventory asset movement?”
- “What taxes do I owe?”
- “What revenue is earned vs still unpaid?”
- “What fees were withheld vs already settled?”
- “What expenses hit the business outside the print job itself?”
- “Can I trust this as bookkeeping data?”

That is the missing layer.

---

## Specific Findings From the Current Codebase

## 1. Financial metrics are mixed with operational metrics

The code stores and reports values like:
- `total_revenue`
- `net_profit`
- `platform_fees`
- `total_cost`
- `net_revenue`

These are useful, but they are currently **business math fields**, not accounting entries.

### Why that matters
A real financial system needs to distinguish between:
- quoted revenue
- invoiced revenue
- collected cash
- recognized revenue
- COGS
- operating expense
- liabilities
- owner draws / equity movements

Right now those concepts are blended together.

---

## 2. Sales profit is overstated in current metrics

In `backend/app/api/v1/endpoints/sales.py`, `total_profit` is returned as:

- `total_revenue - total_cost`

But `total_cost` there is only based on sale item `unit_cost * quantity`.

That means **platform fees and shipping cost are not included in the sales profit metric** even though they are real costs.

### Impact
The dashboard can make the sales side look healthier than it really is.

### Recommendation
Replace the current sales profit logic with one of these explicitly named concepts:
- **gross profit** = sales revenue - item COGS
- **contribution profit** = sales revenue - item COGS - channel fees - shipping cost
- **net sales profit** = contribution profit - allocated overhead

Do not call something “profit” unless the included cost buckets are explicit.

---

## 3. `net_revenue` is semantically mislabeled

In `backend/app/services/sales_service.py`, `net_revenue` is calculated as:

- total
n- minus platform fees
- minus shipping cost
- minus item cost

That is not really “net revenue.”
That is closer to **contribution profit** or **post-fulfillment margin**.

### Recommendation
Rename this field to something clearer, such as:
- `contribution_profit`
- `gross_profit_after_fees`
- `sale_margin_amount`

And reserve `net_revenue` for revenue after discounts/returns but before COGS, or define the term explicitly across the app.

---

## 4. P&L logic likely double counts revenue

The P&L report currently combines:
- `job.total_revenue`
- and `sale.total`

This is a serious accounting design problem.

If a job is used to build inventory and then that inventory is later sold, you should **not** count:
- production-side expected revenue
n- plus sales-side actual revenue

That can overstate revenue and distort profitability.

### Why this matters
A manufacturing business should generally treat:
- **job/production** as inventory creation or WIP movement
- **sale** as revenue recognition event

### Recommendation
For a true financial model:
- jobs should primarily produce **cost accumulation** and inventory value
- sales should drive **revenue recognition**
- reports should clearly separate:
  - operational pricing estimates
  - financial statements

---

## 5. No true COGS recognition model

The app tracks inventory movement and stores product `unit_cost`, which is good.
But there is no formal accounting event for:
- move from inventory asset -> COGS when sold

Right now inventory quantity changes happen, but the financial side is mostly derived, not journalized.

### Recommendation
Introduce explicit accounting treatment for inventory:
- when production completes:
  - debit Finished Goods Inventory
  - credit WIP / Production Clearing
- when sale happens:
  - debit COGS
  - credit Finished Goods Inventory

Even if you do not expose full journal entries to the user at first, the internal financial model should be built this way.

---

## 6. No expense management outside per-job costing

A real 3D printing business has costs that are not job-line inputs:
- filament purchases
- printer purchases
- spare nozzles, beds, parts
- maintenance
- packaging supply purchases
- subscriptions
- advertising
- Etsy ads
- software tools
- rent/utilities
- contractor expenses

Currently the app mostly models **production cost inputs**, not **business expenses**.

### Recommendation
Add:
- vendors
- bills / expenses
- expense categories
- recurring expenses
- receipt attachment support (later)
- paid/unpaid states
- expense-to-account mapping

Without this, the app cannot become a reliable source of true profitability.

---

## 7. No accounts receivable workflow

The app tracks sales but not the finance lifecycle around them.
Missing concepts include:
- quote/estimate
- invoice
- due date
- payment received date
- partial payments
- outstanding balance
- bad debt / write-off

This matters especially for direct/custom B2B or commission print work.

### Recommendation
Create a proper order-to-cash flow:
- **Quote** -> **Job/Order** -> **Invoice** -> **Payment** -> **Settlement**

For custom printing, invoice/payment tracking is a big upgrade.

---

## 8. No accounts payable / purchasing workflow

There is no purchasing flow for acquiring materials or supplies.
For example:
- buying 10 spools from a vendor
- recording landed cost
- shipping cost on supplies
- increasing raw material inventory
- tracking unpaid vendor bills

### Recommendation
Add:
- purchase orders or purchases
- vendor bills
- raw material receiving
- per-lot material costing
- payable status tracking

This is especially important if Brent wants this to feel like software built for a real business rather than a fancy calculator.

---

## 9. Material inventory is operational, not financial

Material records include spool stock and reorder point, which is useful. But there is no strong financial inventory model around raw materials.

### Missing pieces
- purchase history per spool/lot
- landed cost
- lot valuation
- consumption journal
- variance tracking
- waste/scrap costing

### Recommendation
Split inventory into:
- **Raw Materials**
- **Work In Progress**
- **Finished Goods**

This would make the app much more like a real manufacturing/financial platform.

---

## 10. Sales tax is present as a number, but not as a liability system

There is a `tax_collected` field and a `sales_tax_pct` setting, but there is no real tax accounting model.

### Missing pieces
- nexus/jurisdiction logic
- tax liability account
- tax owed vs remitted
- marketplace facilitator logic
- exempt sales
- remittance reporting

### Recommendation
At minimum, introduce:
- `tax_jurisdiction`
- `tax_rate`
- `tax_liability_balance`
- `tax_remittance` records
- distinction between marketplace-collected and seller-collected tax

For Etsy/Amazon/direct sales this matters a lot.

---

## 11. No payout settlement tracking for marketplaces

A 3D print business selling on Etsy/Amazon rarely receives the full order total directly and immediately.
There are usually:
- platform fees
- ad fees
- reserve holds
- shipping label charges
- payout delays
- batch deposits

The current model records channel fees, but not the settlement lifecycle.

### Recommendation
Add:
- settlement batches
- payout date
- deposit amount
- reserve/hold amount
- fee adjustments
- reconciliation against sales/orders

This would make the app much more useful for real business cash tracking.

---

## 12. No audit trail for finance-sensitive edits

For a financial app, users need to know:
- who changed price
- who edited job cost assumptions
- who refunded an order
- who changed an expense
- when inventory was adjusted manually

The code has user auth, but not a true audit log around financial events.

### Recommendation
Add an `audit_log` table for:
- entity type/id
- action
- old values
- new values
- actor
- timestamp
- reason/note

This becomes increasingly important once real money and bookkeeping are involved.

---

## 13. Reports are useful, but not yet accountant-trustworthy

The reports are good operationally, but they need a stronger model before they become “financial reports.”

### Current state
- dashboard: operational summary
- sales report: channel/product trends
- P&L: blended estimate
- inventory report: stock visibility

### Needed upgrade
Separate reporting into two layers:

#### Operational reports
- quoting margins
- printer utilization
- product performance
- material usage
- refund/return rates
- order channel performance

#### Financial reports
- accrual P&L
- cash flow summary
- balance sheet
- A/R aging
- A/P aging
- tax liability
- inventory valuation
- COGS by month
- owner draws/equity changes

Right now the app is strong in the first category and weak in the second.

---

## Recommended Direction

## Keep
- overall UI structure
- page organization
- domain focus on 3D printing
- cost calculator engine
- inventory and sales foundation

## Change
Build a **finance/accounting layer under the existing product**, not a redesign of the layout.

That means:
- keep the current experience familiar
- deepen the data model
- improve terminology
- make reports financially correct

---

# Implementation Roadmap — Part 2

## Phase 11 — Financial Model Cleanup (Must Do First)

### Goals
Fix terminology and reporting semantics before adding more features.

### Work
1. Review and rename misleading financial fields
   - `net_revenue` -> `contribution_profit` or equivalent
   - clearly define gross revenue, net sales, gross profit, net profit

2. Fix sales metrics logic
   - include platform fees and shipping cost in profit views where appropriate
   - expose multiple profit levels instead of one overloaded number

3. Refactor P&L logic
   - stop double counting production-side expected revenue and actual sales revenue
   - separate inventory creation from revenue recognition

4. Add a finance glossary document
   - define every metric used in dashboard and reports

### Deliverables
- corrected metric naming
- corrected report calculations
- finance glossary in docs
- regression tests for all revised formulas

---

## Phase 12 — Accounting Foundation

### Goals
Introduce the minimum structure required for “true financial application” behavior.

### New core entities
- `accounts` (chart of accounts)
- `journal_entries`
- `journal_lines`
- `accounting_periods`

### Suggested starter chart of accounts
#### Assets
- Cash
- Accounts Receivable
- Raw Materials Inventory
- Work In Progress Inventory
- Finished Goods Inventory
- Prepaid Expenses

#### Liabilities
- Accounts Payable
- Sales Tax Payable
- Deferred Revenue / Customer Deposits

#### Equity
- Owner Equity
- Owner Draws
- Retained Earnings

#### Revenue
- Product Sales
- Shipping Income
- Other Income

#### Cost of Goods Sold
- Material COGS
- Labor COGS
- Machine COGS
- Packaging COGS
- Freight-out / Fulfillment

#### Operating Expenses
- Software Subscriptions
- Advertising
- Repairs & Maintenance
- Utilities
- Office / Supplies
- Marketplace Fees

### Deliverables
- accounting schema
- posting rules service
- period locking support (basic)
- seed chart of accounts

---

## Phase 13 — Inventory Accounting

### Goals
Turn inventory from quantity tracking into financially meaningful inventory.

### Work
1. Separate inventory layers
   - raw materials
   - WIP
   - finished goods

2. Track raw material purchases by lot
   - vendor
   - purchase date
   - quantity
   - unit cost
   - freight/landed cost

3. Post accounting events for production
   - raw materials -> WIP
   - WIP -> finished goods

4. Post accounting events for sales
   - finished goods -> COGS

5. Add scrap/waste handling
   - spoilage
   - failed prints
   - rework
   - write-downs

### Deliverables
- inventory valuation rules
- lot/receipt tracking
- accounting postings for production and sale
- inventory valuation report

---

## Phase 14 — Expenses, Vendors, and Payables

### Goals
Capture the real business costs that exist outside a job form.

### New entities
- `vendors`
- `expenses`
- `bills`
- `bill_payments`
- `expense_categories`

### Features
- create expense/bill
- assign vendor
- assign account/category
- attach tax treatment
- due date and paid date
- recurring monthly expenses
- mark reimbursable / owner-paid if needed

### Deliverables
- expenses UI
- vendor management UI
- A/P summary
- expense reporting by category/month

---

## Phase 15 — Invoicing, Payments, and Receivables

### Goals
Support custom print jobs and wholesale customers like a real business.

### New entities
- `quotes`
- `invoices`
- `invoice_lines`
- `payments`
- `customer_credits`

### Features
- quote approval flow
- invoice issuance
- due dates
- partial payments
- payment methods
- payment reconciliation
- outstanding balances
- credit memos / adjustments

### Deliverables
- quote -> invoice -> payment workflow
- A/R aging report
- unpaid invoices dashboard widget
- payment history per customer

---

## Phase 16 — Tax and Marketplace Settlement

### Goals
Model the reality of Etsy/Amazon/direct-channel cash flows.

### New entities
- `tax_profiles`
- `tax_jurisdictions`
- `tax_remittances`
- `marketplace_settlements`
- `settlement_lines`

### Features
- separate seller-collected vs marketplace-collected tax
- track tax liability by period
- import or record marketplace payouts
- reconcile payouts to underlying sales
- reserve/hold/adjustment support

### Deliverables
- tax liability report
- marketplace payout reconciliation screen
- net deposit tracking

---

## Phase 17 — Financial Reporting Layer

### Goals
Make reporting trustworthy and decision-grade.

### Reports to add
1. Balance Sheet
2. Cash Flow Summary
3. Accrual P&L
4. Cash-basis P&L
5. A/R Aging
6. A/P Aging
7. Inventory Valuation
8. COGS by month/product/channel
9. Expense by category/vendor
10. Tax Liability Summary

### Dashboard upgrades
- cash on hand
- unpaid invoices
- unpaid bills
- current month true net income
- inventory asset value
- tax payable
- payout in transit

---

## Phase 18 — Controls, Auditability, and Trust

### Goals
Make the app safer to use as real business software.

### Work
- audit log on all finance-sensitive actions
- approval reason for refunds/manual inventory adjustments
- period close / lock
- soft delete restrictions for posted transactions
- role-based permissions for accounting actions
- export package for accountant/CPA

### Deliverables
- audit log UI
- locked period rules
- safer edit/delete workflow
- finance event history

---

# Suggested Data Model Additions

## High-priority tables
- `accounts`
- `journal_entries`
- `journal_lines`
- `vendors`
- `expenses`
- `bills`
- `payments`
- `invoices`
- `invoice_lines`
- `quotes`
- `marketplace_settlements`
- `tax_remittances`
- `audit_log`

## Important additions to existing entities

### `sales`
Add:
- invoice_id
- payment_status
- payment_received_at
- payout_batch_id
- settlement_status
- discount_amount
- refund_amount
- recognized_revenue_at

### `jobs`
Add:
- production_stage
- actual_start_at
- actual_completed_at
- failure_qty
- scrap_cost
- overhead_allocation_method
- accounting_status

### `products`
Add:
- inventory_account_id
- cogs_account_id
- revenue_account_id
- standard_cost
- valuation_method

### `materials`
Add:
- raw_material_account_id
- preferred_vendor_id
- default_purchase_uom
- average_cost
- last_purchase_cost

---

# UI/Product Recommendations

## New top-level sections to add
- **Finance**
- **Expenses**
- **Invoices**
- **Vendors**
- **Accounting**

## Suggested Finance section pages
1. Overview
2. Profit & Loss
3. Balance Sheet
4. Cash Flow
5. Accounts Receivable
6. Accounts Payable
7. Tax Center
8. Reconciliation
9. Audit Log

## Suggested UX principle
Keep the current clean layout, but introduce **two lenses**:
- **Operations**
- **Finance**

That avoids clutter and keeps the app friendly while still becoming much more serious.

---

# Priority Order If We Want Maximum Impact Fast

## Best order for development

### Priority 1
- fix metric naming and report correctness
- remove double-counting from P&L
- define profit layers clearly

### Priority 2
- add expenses/vendors/bills
- add invoice/payment workflow
- improve tax handling

### Priority 3
- add chart of accounts + journal posting engine
- add inventory accounting treatment
- add financial statements

### Priority 4
- settlement reconciliation
- audit logs
- period close controls

---

# Recommended Build Strategy

## Do not rewrite
This repo does **not** need a rewrite.

## Do this instead
Use the current app as the operational shell and add a true finance engine underneath it in stages.

That is the right move because:
- the domain fit is already good
- the page structure is already usable
- the architecture is extensible
- most of the missing value is in data model + financial logic, not in visual design

---

# Final Recommendation

If the goal is to make this feel like **software built specifically for a real 3D printing business**, then Part 2 should focus on:

1. **financial correctness first**
2. **expenses/AP/AR next**
3. **inventory accounting after that**
4. **formal reporting and auditability last**

The app already looks like a business tool.
What it needs now is to **think like a business system**.

---

# Proposed Next Development Target

## Part 2 scope recommendation
If we want a practical next implementation slice, I recommend the first development batch be:

1. Fix sales/P&L metric semantics
2. Add expense tracking + vendors + bills
3. Add invoicing + payment tracking
4. Add finance dashboard widgets
5. Add audit log foundation

That would produce the fastest visible shift from:
- “smart print calculator/admin app”

to:
- “real 3D printing business management platform with financial backbone”
