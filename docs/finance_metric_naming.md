# Finance Metric Naming Matrix

This document is the canonical source of truth for finance-related metric names used by the application.

## Purpose

The app mixes operational reporting and finance-adjacent reporting. To reduce ambiguity, metric names should describe what they actually represent today.

## Naming Matrix

| Old Name | New Name | Where | Definition |
|---|---|---|---|
| `net_revenue` | `contribution_margin` | Sale detail/list, sales channel breakdown | Sale total minus platform fees, shipping cost, and item-level cost. This is **not** accounting net revenue. |
| `total_revenue` | `gross_sales` | Sales metrics, sales report summary | Total realized sales amount for included completed sales/orders. |
| `total_cost` | `item_cogs` | Sales metrics, sales report summary | Sum of item-level cost basis for sold items. This is product/item COGS only, not full business cost. |
| `total_profit` | `gross_profit` | Sales metrics, sales report summary | Gross sales minus item COGS. This intentionally excludes platform fees and shipping cost in the current implementation. |
| `revenue` | `gross_sales` | Sales report period rows, top products, channel breakdown | Gross realized sales before deducting item COGS or fees. |
| `cost` | `item_cogs` | Sales report period rows, top products | Item-level cost basis used for sold products. |
| `profit` | `gross_profit` | Sales report period rows, top products | Gross sales minus item COGS. |

## Terms intentionally left unchanged for now

### Jobs / Calculator

These values are still operationally useful and remain unchanged in issue #12:

- `total_revenue` — quoted/expected revenue from calculated job pricing
- `net_profit` — quoted/expected net profit after modeled costs and platform fees
- `profit_per_piece` — quoted/expected net profit per finished unit

These names may still be revisited in later phases when operational metrics are more cleanly separated from accounting/reporting metrics.

## Profit Layer Formulas

### Gross Sales
Realized sale total for completed sales/orders included in the view.

### Item COGS
Sum of item-level cost basis for sold items.

### Gross Profit
`gross_sales - item_cogs`

### Contribution Margin
`gross_profit - platform_fees - shipping_costs`

Equivalent sale-level formula:
`total - item_cogs - platform_fees - shipping_cost`

### Net Profit
Not yet exposed for sales reporting because overhead allocation has not been implemented.

## Important Cautions

1. `contribution_margin` is still an operational metric, not a booked accounting statement amount.
2. `gross_profit` in sales reporting means **gross sales - item COGS**.
3. `contribution_margin` means **gross profit - platform fees - shipping costs**.
4. Net profit is intentionally `null`/omitted in the sales layer until overhead allocation exists.
5. P&L semantics are still under review; issue #14 covers statement-level cleanup.

## Related Issues

- #12 — Audit and rename ambiguous financial fields
- #13 — Correct sales profitability metrics and expose layered profit views
- #14 — Refactor P&L reporting to avoid double-counting and separate operational vs financial reporting
