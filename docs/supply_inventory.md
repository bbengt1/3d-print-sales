# Supply Inventory

Supply inventory tracks purchased or shop-supply components used by product BOMs. Supplies are different from filament `materials` and finished `products`: they represent reusable non-filament parts such as LED strips, magnets, screws, heat-set inserts, wiring, switches, adhesives, labels, and packaging hardware.

## Scope

- Supplies are managed from `/stock/supplies`.
- Supply BOM rows can link to a saved supply item.
- Linked supply BOM rows use the supply item for current name, SKU, unit cost, and quantity on hand.
- Updating a supply record updates future BOM cost and buildability summaries without editing every product BOM.
- Supply stock is included in `/api/v1/inventory/alerts` when quantity on hand is at or below reorder point.
- Supply inventory does not post accounting entries or auto-consume stock when finished goods are produced.

## Data Model

`supplies` stores reusable purchased/shop components:

- `name`
- `sku`, optional and unique when present
- `category`, optional
- `unit`
- `unit_cost`
- `quantity_on_hand`
- `reorder_point`
- `supplier`
- `supplier_url`
- `notes`
- `active`

`product_bom_items.supply_id` links a BOM row to supply inventory. Existing inline supply BOM rows remain supported when a one-off component does not need a reusable inventory record.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/supplies` | List supplies with `active`, `category`, `search`, `skip`, and `limit` filters. |
| `POST` | `/api/v1/supplies` | Create a supply. |
| `GET` | `/api/v1/supplies/{supply_id}` | Fetch one supply. |
| `PUT` | `/api/v1/supplies/{supply_id}` | Update a supply. |
| `POST` | `/api/v1/supplies/{supply_id}/adjust` | Adjust quantity on hand. |
| `DELETE` | `/api/v1/supplies/{supply_id}` | Archive a supply. |

Example create payload:

```json
{
  "name": "10x3mm magnet",
  "sku": "MAG-10X3",
  "category": "hardware",
  "unit": "each",
  "unit_cost": 0.18,
  "quantity_on_hand": 200,
  "reorder_point": 25,
  "supplier": "Parts Vendor"
}
```

Example linked BOM row:

```json
{
  "component_type": "supply",
  "supply_id": "00000000-0000-0000-0000-000000000003",
  "quantity": 4,
  "unit": "each",
  "waste_factor_pct": 0
}
```

## Operating Rules

- Use Supplies for reusable purchased components that appear in multiple products.
- Use inline supply BOM rows for one-off parts that do not need inventory tracking yet.
- Use Materials for filament/spool inventory and gram-based print material cost.
- Use Products for finished goods or subassemblies that are stocked and sold or assembled separately.
- Archive supplies instead of deleting them when they have historical BOM references.

## Future Scope

- Supply transaction ledger with actor/reason history.
- Purchase orders and supplier restock workflows.
- Automatic supply consumption when production receipts are created.
- Multi-bin or multi-location supply stock.
