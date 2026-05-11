# Custom Fields

User-defined per-scope fields stored in a side table — the existing record schemas (Customer, Product, etc.) are untouched. Originally #253; computed, multi-value, and per-line scopes added in #326 Phase 2.

## Model

- **`CustomFieldDefinition`**: `scope` × `key` (unique), `name`, `field_type` (text / long_text / number / date / dropdown / checkbox / multi_select / computed), `options` (JSON, used by dropdown and multi_select), `formula` (computed only), `is_required`, `sort_order`, `is_active`.
- **`CustomFieldValue`**: `(definition_id, record_id)` unique. String-stored; coerced on read per type. Computed fields have no row — they're derived at read time.

## Supported scopes

Document scopes: `customer`, `vendor`, `product`, `material`, `supply`, `job`, `sale`, `invoice`, `quote`, `bill`.

Per-line scopes (#326 P2): `sale_item`, `invoice_line`, `quote_line`, `bill_line`, `purchase_order_line`, `sales_order_line`. `record_id` refers to the child line's id.

## Field types

| Type | Storage | API form | Notes |
|---|---|---|---|
| `text`, `long_text` | string | string | |
| `dropdown` | string | string | Validated against `options`. |
| `number` | normalized Decimal string | string | |
| `date` | `YYYY-MM-DD` ISO | `YYYY-MM-DD` | |
| `checkbox` | `"true"` / `"false"` | bool | |
| `multi_select` | JSON-array string | `list[str]` (or comma-string on write) | Validated against `options`. Deduped, order preserved. |
| `computed` | *(no row)* | derived value | `formula` selects a registered evaluator; no writes. |

## Computed-field formulas

| Formula | Argument | Returns |
|---|---|---|
| `days_since:<column>` | A date column on the scope's model. | Whole days from that date to today (`int`). |

Computed fields are read-only — writes to them are silently dropped so generic record-save flows can pass through `{key: raw}` blindly without raising. Required-check is N/A for computed fields. If the evaluator can't resolve the source column (column missing, value null), the field returns `null` rather than 500-ing on the read.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/custom-fields/{scope}` | List definitions for a scope. |
| `POST` | `/api/v1/custom-fields` | Create a definition. Validates `key` slug, dropdown/multi_select options, computed formula. |
| `PATCH` | `/api/v1/custom-fields/{id}` | Update name / options / formula / required / sort_order / active. `field_type` and `scope` are immutable to avoid silent value-corruption. |
| `DELETE` | `/api/v1/custom-fields/{id}` | Soft-deactivate (preserves stored values). |
| `DELETE` | `/api/v1/custom-fields/{id}/hard?force=true` | Hard delete. Refuses by default if any values exist; `force=true` deletes values too. |
| `GET` | `/api/v1/custom-fields/values/{scope}/search?key=…&value=…` | Find record IDs whose value for `{key}` matches. |
| `GET` | `/api/v1/custom-fields/values/{scope}/{record_id}` | Read all values for a record (computed included). |
| `POST` | `/api/v1/custom-fields/values/{scope}/{record_id}` | Upsert values: `{values: {key: raw}}`. Required-field check across active defs. Unknown keys silently ignored. Writes to computed-field keys are silently dropped. |

## Phase 2 follow-ups (still deferred)

- **List filtering** at the master-data list endpoint level (`?cf.{key}=value`) — the dedicated search endpoint covers the lookup, but inline `?cf.*` query-string filters on `/customers`, `/products`, etc. are still on the wishlist.
- **Frontend**: definition CRUD under `/admin` + per-detail-page "Custom" section, including per-line column rendering.
- **Additional computed formulas**: arithmetic between two columns, conditional, etc. Today the registry is just `days_since`.
- **Field-level validation rules** (regex, min/max).

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/custom-fields/{scope}` | List definitions for a scope. |
| `POST` | `/api/v1/custom-fields` | Create a definition. Validates `key` slug, dropdown options, type. |
| `PATCH` | `/api/v1/custom-fields/{id}` | Update name / options / required / sort_order / active. `field_type` and `scope` are immutable to avoid silent value-corruption. |
| `DELETE` | `/api/v1/custom-fields/{id}` | Soft-deactivate (preserves stored values). Hard delete is a Phase 2 follow-up gated on no-values check. |
| `GET` | `/api/v1/custom-fields/values/{scope}/{record_id}` | Read all values for a record. |
| `POST` | `/api/v1/custom-fields/values/{scope}/{record_id}` | Upsert values: `{values: {key: raw}}`. Required-field check across active defs. Unknown keys silently ignored. |

## Coercion

| Field type | Storage | API form |
|---|---|---|
| `text`, `long_text`, `dropdown` | string | string |
| `number` | normalized Decimal string | string |
| `date` | `YYYY-MM-DD` ISO | `YYYY-MM-DD` |
| `checkbox` | `"true"` / `"false"` | bool |

## Phase 2 follow-ups

- **List filtering** by custom field value (`?cf.{key}=value`) on master-data list endpoints.
- **Frontend** definition CRUD under `/admin` + per-detail-page "Custom" section.
- **Hard delete** of definitions (gated on no-values check).
- **Computed fields**, **field-level validation rules** (regex, min/max), **multi-value fields**.
- **Per-line custom fields** (currently only on parent records).
