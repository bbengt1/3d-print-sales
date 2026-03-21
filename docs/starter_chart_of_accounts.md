# Starter Chart of Accounts

This document explains the default chart of accounts seeded for the 3D Print Sales application.

## Purpose

The starter chart of accounts is intended to give a small 3D printing business a sensible manufacturing-aware accounting structure without forcing the owner to build one from scratch.

It is a **starting point**, not a full accountant-customized chart.

## Account Groups

### Assets

#### 1000 — Cash
Use for business cash balances and bank-account cash equivalents.

#### 1100 — Accounts Receivable
Use for customer invoices that have been issued but not yet paid.

#### 1200 — Raw Materials Inventory
Use for consumable material inputs such as filament, resin, packaging stock, and other production materials before they enter production.

#### 1300 — Work In Progress Inventory
Use for partially completed production that has not yet become finished goods.

#### 1400 — Finished Goods Inventory
Use for completed products that are ready to sell.

#### 1500 — Prepaid Expenses
Use for costs paid in advance that benefit future periods.

---

### Liabilities

#### 2000 — Accounts Payable
Use for vendor bills and expenses owed but not yet paid.

#### 2100 — Sales Tax Payable
Use for tax collected from customers that is owed to a tax authority.

#### 2200 — Deferred Revenue
Use for customer deposits or prepayments that are not yet earned revenue.

---

### Equity

#### 3000 — Owner Equity
Use for owner capital contributions and baseline equity balance.

#### 3100 — Owner Draws
Use for owner withdrawals that are not business expenses.

#### 3200 — Retained Earnings
Use for accumulated prior-period earnings retained in the business.

---

### Revenue

#### 4000 — Product Sales
Primary revenue account for product sales.

#### 4100 — Shipping Income
Use when shipping is charged to the customer and tracked separately from product revenue.

#### 4900 — Other Income
Use for income that does not fit the main product-sales workflow.

---

### Cost of Goods Sold

#### 5000 — Material COGS
Use for the direct material cost of products sold.

#### 5100 — Labor COGS
Use for direct production labor included in product cost.

#### 5200 — Machine COGS
Use for machine/runtime/depreciation-style direct production cost assigned to sold output.

#### 5300 — Packaging & Fulfillment
Use for packaging and fulfillment costs directly associated with delivered sales.

---

### Operating Expenses

#### 6000 — Marketplace Fees
Use for Etsy/Amazon/platform selling fees that are not treated as direct COGS.

#### 6100 — Software & Subscriptions
Use for SaaS tools, design software, hosting, and recurring software subscriptions.

#### 6200 — Advertising
Use for paid ads, promoted listings, and marketing spend.

#### 6300 — Repairs & Maintenance
Use for printer repairs, upkeep, and maintenance parts not capitalized into assets.

#### 6400 — Utilities
Use for shop-level utilities not directly tracked as product-level machine cost.

#### 6500 — Office & Supplies
Use for general office/shop supplies that are not direct inventory items.

---

## Design Notes

- Assets, liabilities, equity, revenue, COGS, and operating expenses are all represented.
- Inventory is split into **raw materials**, **WIP**, and **finished goods** to support future manufacturing accounting workflows.
- COGS is separated into material, labor, machine, and fulfillment buckets so future reporting can be more informative.
- Marketplace fees are currently seeded as an expense account rather than a direct revenue contra-account.

## Current Limitations

- The seeded chart does not yet create a deep parent/child hierarchy.
- The starter chart is intentionally lean and may need customization for taxes, loans, payroll, or fixed-asset accounting.
- Future phases may connect products, materials, invoices, and inventory flows directly to specific account IDs.

## Source of Truth

The seeded accounts are currently defined in:
- `backend/app/services/accounting_service.py`

The seed is executed through:
- `backend/app/seed.py`
