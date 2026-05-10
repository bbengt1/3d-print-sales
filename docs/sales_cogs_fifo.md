# Sales-side COGS FIFO (#317)

When a sale completes today, the system posts COGS at the SaleItem's
`unit_cost` snapshot — taken at sale-creation time, typically equal to
`Product.unit_cost` at that moment. This is fast and predictable but
ignores the actual cost of the inventory layer the unit was drawn
from. After running production for a few months that drift becomes
visible: rising material prices mean recent layers cost more than the
snapshot, and your reported gross margin lags reality.

The FIFO rewrite (#317) draws COGS from `FinishedGoodsLayer` rows in
oldest-first order at their actual layer cost. The behavior is
**feature-flagged** — installations stay on the legacy snapshot path
until an operator explicitly opts in.

## Enable / disable

Admin endpoint:

```http
GET /api/v1/cogs/fifo-flag
PUT /api/v1/cogs/fifo-flag      body: {"enabled": true|false}
```

Backed by Setting key `cogs.fifo_consumption_on_sale_enabled` (string
`"true"`/`"false"`). Default off.

## Dry-run preview

Before flipping the flag on, sanity-check a representative sale:

```http
GET /api/v1/cogs/sales/{sale_id}/fifo-dry-run
```

Returns:

```json
{
  "sale_id": "…",
  "snapshot_cogs": 6.0000,    // what was posted under legacy
  "fifo_cogs": 12.5000,       // what would post under FIFO
  "fifo_from_layers": 12.5000,
  "fifo_from_snapshot": 0.0000,
  "variance": 6.5000          // fifo - snapshot
}
```

If `variance` is large in absolute terms across many sales, the FIFO
path will produce noticeably different gross margin once enabled.
That's expected and correct — but you may want to coordinate with
whoever consumes those reports before flipping the flag.

## Behavior with flag ON

For each `SaleItem` linked to a `Product`:

1. Walk that product's `FinishedGoodsLayer` rows ordered by `created_at`
   ascending.
2. Take min(layer.qty_remaining, requested_qty) from each layer; the
   COGS contribution is `taken_qty × layer.unit_cost`. Decrement the
   source layer's `qty_remaining` accordingly.
3. If the layers run out before satisfying the requested quantity, the
   remainder falls back to `item.unit_cost × uncovered_qty` (the
   legacy snapshot path).

The single Dr COGS / Cr Finished Goods JE then posts the **summed**
amount.

## What's still deferred

- **Variance accounting**: today the actual layer cost is the COGS.
  When a "standard cost" concept exists (e.g. operator sets
  `Product.standard_cost`), variance posting to a 5500 "Inventory
  Variance" account becomes meaningful — until then it's just noise.
- **Refund-side FIFO restoration**: refunds today restore stock to
  `Product.stock_qty` and credit at `item.unit_cost`. Restoring to a
  specific layer (or recreating one) is design-deferred since refunds
  are rare and the difference rounds out across periods.
- **Hourly overhead layers** (machine + labor cost rolled into the
  produced FinishedGoodsLayer at production close) — covered by the
  production-side rewrite, not the sales-side path.
- **Supply FIFO** — supplies don't currently produce layers; their
  cost still flows from `Supply.unit_cost` snapshots.
- **Job link on consumption rows** — the `LayerDraw` records aren't
  persisted as a separate audit table yet. The JE memo carries the
  FIFO breakdown; we'd add a `SaleConsumption` table when there's a
  reporting need that the JE memo can't satisfy.
