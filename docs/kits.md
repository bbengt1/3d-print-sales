# Inventory Kits (Phase 1)

#262's kit piece. A product is treated as a "kit" whenever it has at least one row in `kit_components` linking it to other products with quantities. No new column on Product needed.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/kits/{kit_product_id}` | Get the kit definition (component list) for a product. |
| `PUT` | `/api/v1/kits/{kit_product_id}` | Define or replace the kit's component list. Body: `{components: [{component_product_id, quantity}, ...]}`. Self-reference is rejected. Each component product must exist. |
| `DELETE` | `/api/v1/kits/{kit_product_id}` | Remove all components → the product stops being a kit. |
| `GET` | `/api/v1/kits` | List all kit products (distinct `kit_product_id` values). |

## Phase 2 follow-ups

- **Sale-time explosion**: when a kit is sold, decrement each component's stock and post COGS for each component instead of for the kit itself. Wire into `sales_service.py`. Today the kit is treated like any other product at sale time — define-only Phase 1.
- **Nested kits** (a kit containing another kit). Phase 1 rejects self-reference but doesn't transitively check for cycles.
- **Find-and-merge duplicate items** (still ❌ from #262 original scope — separate issue).
- **Inventory starting-balances CSV import** (still ❌ from #262 original scope — overlaps with #260's starting-balances workflow but for inventory).
- **Frontend** kit editor on Product detail page.
