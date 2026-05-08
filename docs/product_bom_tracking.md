# Product BOM Tracking

Product Studio supports a direct bill of materials (BOM) for finished products. A BOM row can reference a raw material, another stocked product, or a generic purchased/shop-supply component, which lets operators describe the parts required to build a sellable product without forcing every component into the older single-material product field.

## Scope

- BOM rows are edited from `/product-studio/products/:id/edit`.
- Read-only cost, buildability, and blocker status is shown on `/product-studio/products/:id`.
- A component can be a material, a finished product, or a generic supply.
- Material rows support gram-based quantities (`g`, `gram`, `grams`) and use `materials.cost_per_g` for estimated cost.
- Non-gram material rows use spool count and `materials.spool_price`.
- Product rows use component product stock and current product `unit_cost`.
- Supply rows support purchased parts such as LED strips, magnets, screws, heat-set inserts, wiring, switches, and adhesives.
- Supply rows can link to reusable supply inventory or store one-off inline component details.
- Linked supply rows use the supply inventory item for current name, SKU, unit cost, and available quantity.
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
    },
    {
      "component_type": "supply",
      "supply_id": "00000000-0000-0000-0000-000000000003",
      "quantity": 4,
      "unit": "each",
      "waste_factor_pct": 0,
      "notes": "Press-fit after print cleanup"
    }
  ]
}
```

## Validation Rules

- A material row must reference exactly one material and no component product.
- A product row must reference exactly one component product and no material.
- A supply row must either reference a saved `supply_id` or include an inline component name.
- Linked supply rows cannot reference a material or product and cannot override the component name.
- Quantity must be greater than zero.
- Waste percentage cannot be negative.
- Supply unit cost cannot be negative.
- Supply available quantity cannot be negative when provided.
- Duplicate component rows are rejected.
- A product cannot include itself.
- Circular product dependencies are rejected, including indirect cycles.

## Buildability

Buildable quantity is calculated from current stock only:

- material grams: `spools_in_stock * net_usable_g`
- other material units: `spools_in_stock`
- product components: `stock_qty`
- linked supply components: `supplies.quantity_on_hand`
- inline supply components: `available_quantity` when provided

Each row with known availability divides available quantity by required quantity, where required quantity includes waste. The product-level buildable quantity is the minimum known row result. Inline supply rows with unknown availability are included in estimated cost but do not constrain buildable quantity. Missing stock, inactive materials, archived component products, inactive linked supplies, and insufficient known supply quantity are reported as blockers.

## Data Model

`product_bom_items` stores one row per direct component:

- `product_id` is the parent finished product.
- `component_type` is `material`, `product`, or `supply`.
- `material_id` or `component_product_id` identifies the component.
- `supply_id` links a supply row to reusable supply inventory.
- `component_name`, `component_sku`, `unit_cost`, and `available_quantity` describe inline one-off supply rows.
- `quantity`, `unit`, and `waste_factor_pct` describe per-unit build requirements.
- `notes` holds operator-facing production context.

See [Supply Inventory](supply_inventory.md) for reusable purchased/shop component tracking. Future production workflows can consume this BOM when creating production receipts, but that ledger behavior is intentionally out of scope for the current Product Studio tracking slice.
