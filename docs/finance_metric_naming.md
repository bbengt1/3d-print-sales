# Finance Glossary and Metric Naming

This document is the canonical source of truth for finance-related terminology used by the application.

## Purpose

The app includes both:
- **operational metrics** used for quoting, pricing, production planning, and shop-floor decisions
- **finance-adjacent metrics** used for sales reporting and business performance review

These are not always the same thing.

This glossary exists to make sure every exposed metric has:
- a plain-English definition
- its current formula/source
- the context where it should be used
- any important cautions about accounting meaning

---

## Core Principle

### Operational vs Financial Metrics

The app currently supports both lenses:

#### Operational metrics
Used for:
- estimating jobs
- setting prices
- understanding production economics
- tracking margins on a quote or print run

These often come from:
- job calculations
- cost calculator outputs
- expected/quoted pricing models

#### Financial metrics
Used for:
- sales reporting
- P&L-style reporting
- understanding realized business performance

These come primarily from:
- completed sales
- recorded fees/shipping costs
- report aggregation logic

### Important rule
A number can be operationally useful without being a booked accounting amount.

---

## Naming Matrix

| Old Name | New Name | Where | Definition |
|---|---|---|---|
| `net_revenue` | `contribution_margin` | Sale detail/list, sales channel breakdown | Sale total minus platform fees, shipping cost, and item-level cost. This is **not** accounting net revenue. |
| `total_revenue` | `gross_sales` | Sales metrics, sales report summary | Total realized sales amount for included completed sales/orders. |
| `total_cost` | `item_cogs` | Sales metrics, sales report summary | Sum of item-level cost basis for sold items. This is product/item COGS only, not full business cost. |
| `total_profit` | `gross_profit` | Sales metrics, sales report summary | Gross sales minus item COGS. |
| `revenue` | `gross_sales` | Sales report period rows, top products, channel breakdown | Gross realized sales before deducting item COGS or fees. |
| `cost` | `item_cogs` | Sales report period rows, top products | Item-level cost basis used for sold products. |
| `profit` | `gross_profit` | Sales report period rows, top products | Gross sales minus item COGS. |
| job-side `total_revenue` in P&L | `operational_production_estimate` | P&L report | Job-side quoted/expected production revenue shown for operational context only, not counted as realized financial revenue. |

---

## Revenue Terms

### Gross Sales
**Definition:**
Realized sale total for completed sales/orders included in the sales reporting view.

**Current source:**
- sales endpoints
- sales report summary
- sales report period rows
- sales report product/channel breakdowns

**Formula:**
`sum(sale.total)` across included completed sales

**Use for:**
- sales reporting
- channel comparison
- product sales reporting

**Do not confuse with:**
- job-side quoted revenue
- accounting net revenue

---

### Sales Revenue
**Definition:**
Revenue recognized by the current P&L report from completed sales only.

**Current source:**
- P&L summary
- P&L period rows

**Formula:**
`sum(completed sale.total)` for the selected period

**Use for:**
- current P&L report basis

---

### Operational Production Estimate
**Definition:**
Job-side quoted/expected production revenue used for operational context.

**Current source:**
- P&L summary
- P&L period rows

**Formula:**
`sum(job.total_revenue)` for jobs in the selected period

**Important caution:**
This value is **excluded** from `total_revenue` in the P&L report to avoid double counting realized sales and production-side expected revenue.

**Use for:**
- operational analytics
- understanding what production work was estimated to generate
- comparing shop activity against realized sales later

---

### Total Revenue
**Definition:**
The current P&L report’s revenue basis.

**Current behavior:**
`total_revenue = sales_revenue`

**Important caution:**
In the P&L report, `total_revenue` intentionally excludes `operational_production_estimate`.

---

## Cost Terms

### Item COGS
**Definition:**
Item-level cost basis for sold products in sales reporting.

**Formula:**
`sum(sale_item.unit_cost * sale_item.quantity)`

**Current scope:**
Sales reporting only.

**Important caution:**
This is not yet a full general-ledger inventory/COGS workflow. It is a derived sales-cost measure based on stored item cost.

---

### Material Costs
**Definition:**
Production/job-side material cost accumulation included in the current P&L view.

**Formula/source:**
`sum(job.material_cost)`

---

### Labor Costs
**Definition:**
Production/job-side labor-related cost accumulation included in the current P&L view.

**Formula/source:**
`sum(job.labor_cost + job.design_cost)`

---

### Machine Costs
**Definition:**
Production/job-side machine and electricity-related cost accumulation included in the current P&L view.

**Formula/source:**
`sum(job.machine_cost + job.electricity_cost)`

---

### Overhead Costs
**Definition:**
Job-side modeled overhead included in current P&L reporting.

**Formula/source:**
`sum(job.overhead)`

**Important caution:**
This is modeled operational overhead from the job calculator, not yet a complete accounting overhead allocation engine.

---

### Platform Fees
**Definition:**
Marketplace/platform costs charged on sales.

**Current source:**
- sale detail
- sales metrics
- sales report
- P&L

**Formula/source:**
Recorded on sale records from configured sales channel fee logic.

---

### Shipping Costs
**Definition:**
Shipping cost borne by the business for a sale.

**Current source:**
- sale detail
- sales metrics
- sales report
- P&L

**Formula/source:**
Recorded on sale records.

---

### Total Costs
**Definition:**
The total cost bucket included in the current P&L report.

**Formula:**
`material_costs + labor_costs + machine_costs + overhead_costs + platform_fees + shipping_costs`

**Important caution:**
This P&L still depends on job-side modeled production costs and sale-side fee/shipping data. It is more correct than before, but not yet a full accounting ledger.

---

## Profit Layers

### Gross Profit
**Definition:**
Sales-layer profit before platform fees and shipping costs.

**Formula:**
`gross_sales - item_cogs`

**Where used:**
- sale detail
- sales metrics
- sales report

---

### Contribution Margin
**Definition:**
Sales-layer profit after item COGS, platform fees, and shipping costs.

**Formula:**
`gross_profit - platform_fees - shipping_costs`

Equivalent sale-level formula:
`total - item_cogs - platform_fees - shipping_cost`

**Where used:**
- sale detail
- sale list
- sales metrics
- sales report

**Important caution:**
This is still an operational/business-performance metric, not a formal accounting net income amount.

---

### Net Profit
**Definition:**
Currently used in the job calculator / job records as quoted or modeled profit after included modeled costs and platform fees.

**Job/calculator formula:**
`job.total_revenue - job.total_cost - job.platform_fees`

**Sales-layer status:**
Not currently exposed in sales reporting because overhead allocation and broader accounting treatment are not yet implemented.

**Important caution:**
`net_profit` in jobs/calculator is not the same thing as a finalized accounting net income figure.

---

### Profit Margin %
**Definition:**
P&L gross profit percentage based on the current report revenue basis.

**Current P&L formula:**
`gross_profit / total_revenue * 100`

Since current P&L `total_revenue` is sales-based only, this margin is also sales-based.

---

## Jobs and Calculator Terms

These fields remain intentionally unchanged for now because they are still useful for operational estimating:

- `total_revenue` — quoted/expected revenue from calculated job pricing
- `net_profit` — quoted/expected net profit after modeled costs and platform fees
- `profit_per_piece` — quoted/expected net profit per finished unit
- `price_per_piece` — recommended or calculated selling price per unit
- `total_cost` — full modeled production cost for the job

**Important caution:**
These are **operational estimate fields**, not yet booked accounting values.

---

## Inventory Terms

### Stock Value
**Definition:**
Current estimated inventory value shown in inventory reporting.

**Current formula/source:**
Generally derived from on-hand quantity and stored unit cost.

### Inventory Turnover
**Definition:**
An operational inventory performance metric comparing sold quantity to stock position.

**Use for:**
- identifying fast/slow-moving products
- reorder planning

### Low Stock
**Definition:**
A product/material state where current stock has crossed the configured reorder threshold.

**Use for:**
- operational replenishment
- not a financial statement metric

---

## Tax Terms

### Tax Collected
**Definition:**
Sales tax amount recorded on a sale.

**Current caution:**
The app records tax collected, but it does not yet implement a full tax liability/remittance workflow.

### Sales Tax Payable
**Definition:**
Planned future accounting concept for tax liability tracking.

**Status:**
Not yet implemented as a true liability workflow.

---

## Dashboard Metrics

### Dashboard Total Revenue
**Definition:**
Dashboard summary revenue currently sourced from jobs, not from sales.

**Important caution:**
This is an operational dashboard metric today, not the same thing as P&L `total_revenue`.

### Dashboard Net Profit
**Definition:**
Dashboard summary net profit currently sourced from jobs.

**Important caution:**
This reflects job-side modeled profitability, not full accounting net income.

---

## P&L Reporting Basis

The current P&L report should be interpreted as:

- **Revenue basis:** realized sales only
- **Production/job data:** operational production estimate + cost accumulation context
- **Double counting rule:** job-side expected revenue is excluded from `total_revenue`

### Reporting basis field
`reporting_basis = sales_realized_revenue`

### Production estimate note
`production_estimate_note` explains why production estimate is shown but excluded from financial revenue.

---

## Current Limitations

1. `contribution_margin` is not a booked accounting statement amount.
2. `item_cogs` is derived from stored sale item cost, not yet a formal inventory accounting posting workflow.
3. Job-side profitability metrics remain estimate/model-driven.
4. Dashboard revenue/profit metrics and P&L revenue/profit metrics are not yet fully unified under one accounting layer.
5. Tax, A/R, A/P, journal entries, and ledger-based financial reporting are still future phases.

---

## Related Issues

- #12 — Audit and rename ambiguous financial fields
- #13 — Correct sales profitability metrics and expose layered profit views
- #14 — Refactor P&L reporting to avoid double-counting and separate operational vs financial reporting
- #15 — Add finance glossary and metric definition documentation
