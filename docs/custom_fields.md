# Custom Fields (Phase 1)

User-defined per-scope fields stored in a side table — the existing record schemas (Customer, Product, etc.) are untouched. #253.

## Model

- **`CustomFieldDefinition`**: `scope` × `key` (unique), `name`, `field_type` (text / long_text / number / date / dropdown / checkbox), `options` (JSON, for dropdown), `is_required`, `sort_order`, `is_active`.
- **`CustomFieldValue`**: `(definition_id, record_id)` unique. String-stored; coerced on read per type.

## Supported scopes (Phase 1)

`customer`, `vendor`, `product`, `material`, `supply`, `job`, `sale`, `invoice`, `quote`, `bill`.

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
