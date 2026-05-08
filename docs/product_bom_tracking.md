# Product BOM Tracking

Product Studio supports a direct bill of materials (BOM) for finished products. A BOM row can reference either a raw material or another stocked product, which lets operators describe the parts required to build a sellable product without forcing those parts into the older single-material product field.

## Scope

- BOM rows are edited from `/product-studio/products/:id/edit`.
- Read-only cost, buildability, and blocker status is shown on `/product-studio/products/:id`.
- A component can be a material or a finished product.
- Material rows support gram-based quantities (`g`, `gram`, `grams`) and use `materials.cost_per_g` for estimated cost.
- Non-gram material rows use spool count and `materials.spool_price`.
- Product rows use component product stock and current product `unit_cost`.
- Waste percentage increases the required quantity and estimated component cost.
- BOM editing does not consume inventory, create production receipts, or update accounting ledgers.

## API Contract

The maintained endpoints live under the product API:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/products/{product_id}/bom` | Return saved BOM rows, estimated unit cost, buildable quantity, and blockers. |
| `PUT` | `/api/v1/products/{product_id}/bom` | Replace all BOM rows for a product. Requires authentication. |
| `GET` | `/api/v1/products/{product_id}/bom/availability` | Return the same BOM summary for availability-oriented callers. |

Example replace payload:

```json
{
  "items": [
    {
      "component_type": "material",
      "material_id": "00000000-0000-0000-0000-000000000001",
      "quantity": 125,
      "unit": "g",
      "waste_factor_pct": 8,
      "notes": "Body and support waste"
    },
    {
      "component_type": "product",
      "component_product_id": "00000000-0000-0000-0000-000000000002",
      "quantity": 2,
      "unit": "each",
      "waste_factor_pct": 0
    }
  ]
}
```

## Validation Rules

- A material row must reference exactly one material and no component product.
- A product row must reference exactly one component product and no material.
- Quantity must be greater than zero.
- Waste percentage cannot be negative.
- Duplicate component rows are rejected.
- A product cannot include itself.
- Circular product dependencies are rejected, including indirect cycles.

## Buildability

Buildable quantity is calculated from current stock only:

- material grams: `spools_in_stock * net_usable_g`
- other material units: `spools_in_stock`
- product components: `stock_qty`

Each row divides available quantity by required quantity, where required quantity includes waste. The product-level buildable quantity is the minimum row result. Missing stock, inactive materials, and archived component products are reported as blockers.

## Data Model

`product_bom_items` stores one row per direct component:

- `product_id` is the parent finished product.
- `component_type` is `material` or `product`.
- `material_id` or `component_product_id` identifies the component.
- `quantity`, `unit`, and `waste_factor_pct` describe per-unit build requirements.
- `notes` holds operator-facing production context.

Future production workflows can consume this BOM when creating production receipts, but that ledger behavior is intentionally out of scope for the current Product Studio tracking slice.
