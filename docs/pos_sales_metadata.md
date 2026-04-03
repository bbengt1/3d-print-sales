# POS Sales Metadata Contract

This document records the storage and reporting contract for POS sales.

## Canonical Storage

POS checkout does not create a parallel POS-only data model.

Instead, POS sales are stored in the standard:
- `sales`
- `sale_items`
- `sales_channels`

tables and reuse the existing inventory and refund foundations.

## POS Identification

POS sales are identified by a dedicated sales channel:
- channel name: `POS`

That channel is the source-of-truth marker for distinguishing POS transactions from marketplace or other direct-sale flows.

## Payment Method

Payment method is stored directly on the `sales.payment_method` field.

Current examples:
- `cash`
- `card`
- `other`

The field is intentionally first-class sale data rather than opaque JSON metadata so standard operational and reporting surfaces can expose it directly.

## Customer Handling

POS checkout supports both:
- guest checkout with `customer_name` only
- customer-linked checkout with `customer_id`

Guest POS sales should remain valid sales records without requiring a customer entity.

## Reporting / API Expectations

Standard sales surfaces should expose POS metadata without requiring special-case interpretation:

- sale detail responses include:
  - `channel_id`
  - `channel_name`
  - `payment_method`
- sale list responses include:
  - `channel_id`
  - `channel_name`
  - `payment_method`
- sales metrics support filtering by:
  - `channel_id`
  - `payment_method`
- sales reports support filtering by:
  - `channel_id`
  - `payment_method`
- sales metrics and reports include grouped views that make POS activity visible through:
  - channel breakdown
  - payment method breakdown

## Inventory Rule for POS

POS is intended to be a cashier workflow, so it should not silently oversell stock.

Current POS inventory rule:
- product-backed POS checkout is blocked when requested quantity exceeds available `stock_qty`
- the checkout should fail before any sale or inventory transaction is committed
- multi-line POS checkout should behave all-or-nothing when any product-backed line is short on stock

This rule keeps POS operationally predictable and avoids silently recording stock movement that the system could not actually fulfill.

## Related Areas

- POS backend checkout foundation: issue `#65`
- POS metadata/reporting contract: issue `#67`
- POS inventory enforcement: issue `#68`
