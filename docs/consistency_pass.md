# Cross-Cutting Consistency Pass (#264)

#264 Phase 1 ships the **shared list-query helper** as the foundation for the four-piece original scope. The other three pieces (form templates, archive flag audit, PDF parity) are documented here as Phase 2 follow-ups so future sessions know what's left.

## What this PR ships

A reusable `app.api.list_query` module with:

- **`ListQuery`** — a Pydantic dependency model for the standard query parameters.
- **`list_query_dep`** — FastAPI `Depends`-style constructor.
- **`apply_list_query(stmt, model, lq, *, allowed_sort, search_columns, allowed_filters, extra_filters)`** — composes a `select` with sort + search + pagination + filters. Returns a `ListQueryResult` carrying the composed statement and pagination metadata.

### Standard query parameter conventions

| Param | Meaning | Example |
|---|---|---|
| `q` | Free-text search across `search_columns` (ILIKE) | `?q=acme` |
| `sort` | Comma-separated columns; `-` prefix for desc | `?sort=-created_at,name` |
| `page` | 1-indexed page number | `?page=3` |
| `page_size` | Rows per page; capped at `MAX_PAGE_SIZE=200`; default `DEFAULT_PAGE_SIZE=50` | `?page_size=25` |
| `?{field}=v` | Equality filter (only for fields in `allowed_filters`) | `?is_active=true` |
| `?{field}__in=a,b,c` | Membership filter | `?status__in=draft,issued` |

### Defensive behavior

- Sort columns not in `allowed_sort` are silently dropped (so a malicious `sort=hashed_password` can't access arbitrary columns or leak the column existence).
- Filter params not in `allowed_filters` are silently dropped.
- Filter param `__in=` empty/blank values are skipped.

### Adoption

**No existing endpoints are modified by this PR.** They keep their bespoke shape until they're refactored to use the helper. New endpoints should adopt it from the start. Phase 2 of #264 retrofits the existing list endpoints incrementally.

Example:

```python
from fastapi import Depends, Query
from app.api.list_query import ListQuery, apply_list_query, list_query_dep

@router.get("/widgets")
async def list_widgets(
    user: CurrentUser,
    db: DB,
    lq: ListQuery = Depends(list_query_dep),
    is_active: bool | None = Query(None),
):
    stmt = select(Widget)
    result = apply_list_query(
        stmt, Widget, lq,
        allowed_sort=["name", "created_at"],
        search_columns=["name", "sku"],
        allowed_filters={"is_active": "is_active"},
        extra_filters={"is_active": is_active},
    )
    rows = (await db.execute(result.stmt)).scalars().all()
    return {"page": result.page, "page_size": result.page_size, "rows": [...]}
```

## Phase 2 follow-ups (the rest of #264)

Each is its own multi-PR effort and best done as a focused issue.

### Form defaults / templates

Per-form save-as-template + apply-on-create system extending `settings_defaults.py`. Scopes: invoice, quote, sales_order, purchase_order, bill, expense_claim, journal_entry. New endpoint family `/api/v1/form-templates`. Default template auto-applies on the create form unless the operator picks another or "blank."

### Inactive / archived flag audit

Standardize on a uniform `archived_at` (datetime, nullable, indexed) timestamp pattern across every master-data table:

- `customer` (no flag today — needs `archived_at`)
- `vendor` (uses `is_active` — migrate to `archived_at` with compatibility property)
- `product` (uses `is_active`)
- `material` (no flag today)
- `supply` (uses `active`)
- `sales_channel`, `tax_profile`, `expense_category`, `account`, `division`, `project` — audit each.

List endpoints exclude archived rows by default with `?include_archived=true` opt-in. Archive/restore actions audit-logged.

### Search/sort UX consistency (frontend side)

A shared `useListQuery` React hook so URL state, debounce, and pagination UI behave identically across every list page. The backend convention is now in place — frontend adoption is a separate sweep.

### PDF generation parity

Audit every printable document (invoice, quote, sales_order, purchase_order, bill, credit_note, debit_note, delivery_note, expense_claim, statement). Establish one shared template scaffold (`templates/pdf/_base.html` with content blocks) and migrate each doc onto it. Visual styling matches across documents (header, footer, business chrome). Replace any browser-print-only HTML output with WeasyPrint where appropriate. **Soft-depends on #244 Phase 2** (which lands the WeasyPrint dep).
