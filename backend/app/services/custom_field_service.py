"""Custom-field validation + storage (#253).

Phase 1: values stored in `custom_field_values` (separate table). Each
scope's existing record table is untouched. Trade-off: fetching values
requires a JOIN, but no migration of every record table.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_field import CustomFieldDefinition, CustomFieldValue


class CustomFieldError(RuntimeError):
    pass


VALID_SCOPES = {
    "customer", "vendor", "product", "material", "supply",
    "job", "sale", "invoice", "quote", "bill",
    # #326 P2: per-line scopes. record_id refers to the child line's id.
    "sale_item", "invoice_line", "quote_line", "bill_line",
    "purchase_order_line", "sales_order_line",
}

FIELD_TYPES = {
    "text", "long_text", "number", "date", "dropdown", "checkbox",
    # #326 P2:
    "multi_select",  # list of strings drawn from `options`
    "computed",      # evaluated at read time via the formula registry
}

# Computed-field formula registry. Each entry maps a formula key to a
# resolver `(db, scope, record_id, arg) -> Any`. Keep the registry small
# and pure — no business rules, just calculator-style derivations.
COMPUTED_FORMULAS: dict[str, str] = {
    # days_since:<scope-specific source date column>
    # Currently supports any scope whose record exposes one of the well-known
    # date columns: invoice_date, sale_date, date, issue_date, posted_date.
    "days_since": "Whole days from <arg> column on the record to today.",
}

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_definition(
    *,
    scope: str,
    key: str,
    field_type: str,
    options: list | None,
    formula: str | None = None,
) -> None:
    if scope not in VALID_SCOPES:
        raise CustomFieldError(f"Unsupported scope: {scope!r}")
    if not _KEY_RE.match(key):
        raise CustomFieldError(
            "key must start with a lowercase letter and contain only [a-z0-9_]"
        )
    if field_type not in FIELD_TYPES:
        raise CustomFieldError(f"Unknown field_type: {field_type!r}")
    if field_type in ("dropdown", "multi_select"):
        if not options or not isinstance(options, list) or not all(isinstance(o, str) and o for o in options):
            raise CustomFieldError(
                f"{field_type} field_type requires non-empty options: list[str]"
            )
    if field_type == "computed":
        if not formula:
            raise CustomFieldError("computed field_type requires a formula")
        # Format: `<formula_key>:<arg>` (arg required for all current formulas).
        head, _, arg = formula.partition(":")
        if head not in COMPUTED_FORMULAS:
            raise CustomFieldError(
                f"Unknown formula {head!r}; supported: {sorted(COMPUTED_FORMULAS)}"
            )
        if not arg:
            raise CustomFieldError(
                f"formula {head!r} requires an argument; got {formula!r}"
            )


def coerce_value(field_type: str, raw: Any, options: list | None) -> str | None:
    """Validate a user-supplied value and return its canonical string form
    for storage. Returns None for empty input."""
    if raw is None or raw == "":
        return None
    if field_type in ("text", "long_text"):
        return str(raw)
    if field_type == "number":
        try:
            return str(Decimal(str(raw)))
        except (InvalidOperation, ValueError) as e:
            raise CustomFieldError(f"Invalid number value: {raw!r}") from e
    if field_type == "date":
        if isinstance(raw, date):
            return raw.isoformat()
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d").date().isoformat()
        except ValueError as e:
            raise CustomFieldError(f"Invalid date value (expected YYYY-MM-DD): {raw!r}") from e
    if field_type == "checkbox":
        if isinstance(raw, bool):
            return "true" if raw else "false"
        s = str(raw).lower()
        if s in ("true", "1", "yes"):
            return "true"
        if s in ("false", "0", "no"):
            return "false"
        raise CustomFieldError(f"Invalid checkbox value: {raw!r}")
    if field_type == "dropdown":
        if not options or str(raw) not in options:
            raise CustomFieldError(f"Value {raw!r} is not in the configured options")
        return str(raw)
    if field_type == "multi_select":
        # Accept list[str] or comma-separated string; store as JSON-array
        # string so we round-trip cleanly and avoid ambiguity around
        # commas inside option labels.
        import json
        if isinstance(raw, str):
            items = [p.strip() for p in raw.split(",") if p.strip()]
        elif isinstance(raw, (list, tuple, set)):
            items = [str(x).strip() for x in raw if str(x).strip()]
        else:
            raise CustomFieldError(f"multi_select expects list or comma-string, got {type(raw).__name__}")
        if not options:
            raise CustomFieldError("multi_select requires options on the definition")
        unknown = [i for i in items if i not in options]
        if unknown:
            raise CustomFieldError(
                f"multi_select values not in options: {unknown}"
            )
        # Deduplicate while preserving order.
        seen: set[str] = set()
        deduped: list[str] = []
        for i in items:
            if i not in seen:
                seen.add(i)
                deduped.append(i)
        return json.dumps(deduped)
    if field_type == "computed":
        raise CustomFieldError("computed fields are read-only and cannot be set directly")
    raise CustomFieldError(f"Unhandled field_type: {field_type}")


def decode_value(field_type: str, stored: str | None) -> Any:
    """Reverse of coerce — return native Python representation for the API."""
    if stored is None:
        return None
    if field_type in ("text", "long_text", "dropdown"):
        return stored
    if field_type == "number":
        return str(Decimal(stored))
    if field_type == "date":
        return stored  # ISO string
    if field_type == "checkbox":
        return stored == "true"
    if field_type == "multi_select":
        import json
        try:
            return json.loads(stored)
        except json.JSONDecodeError:
            return []
    return stored


async def list_definitions(
    db: AsyncSession, *, scope: str, include_inactive: bool = False
) -> list[CustomFieldDefinition]:
    if scope not in VALID_SCOPES:
        raise CustomFieldError(f"Unsupported scope: {scope!r}")
    stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.scope == scope).order_by(
        CustomFieldDefinition.sort_order, CustomFieldDefinition.created_at
    )
    if not include_inactive:
        stmt = stmt.where(CustomFieldDefinition.is_active == True)  # noqa: E712
    return list((await db.execute(stmt)).scalars().all())


async def upsert_values(
    db: AsyncSession,
    *,
    scope: str,
    record_id: uuid.UUID,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Set values for a record. `values` is `{key: raw_value}` for ACTIVE
    definitions only. Required-field check runs across all active defs in
    scope. Returns the canonical decoded values for the record after the
    upsert.
    """
    defs = await list_definitions(db, scope=scope, include_inactive=False)
    by_key = {d.key: d for d in defs}

    # Required-field check: a required field must have a non-empty value.
    # Either the caller submits a non-empty value in this payload, or there
    # must already be a non-empty value stored. Submitting None / "" / [] for
    # a required key is rejected so required fields cannot be silently
    # cleared (or created empty).
    def _is_empty(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str) and v == "":
            return True
        if isinstance(v, (list, tuple, set, dict)) and len(v) == 0:
            return True
        return False

    for d in defs:
        if not d.is_required:
            continue
        if d.field_type == "computed":
            # Computed values are always derived; required-check is N/A.
            continue
        if d.key in values:
            if _is_empty(values[d.key]):
                raise CustomFieldError(
                    f"Required custom field cannot be empty: {d.key}"
                )
        else:
            if not await _has_existing_value(db, d.id, record_id):
                raise CustomFieldError(f"Required custom field missing: {d.key}")

    # Coerce + upsert
    for key, raw in values.items():
        if key not in by_key:
            # Unknown key — silently ignore so client API stays loose
            continue
        d = by_key[key]
        if d.field_type == "computed":
            # Computed fields are derived at read time; ignore writes silently
            # rather than raising, so a generic upsert payload that includes
            # the field doesn't fail on an otherwise-unrelated record save.
            continue
        canonical = coerce_value(d.field_type, raw, d.options)
        existing = (
            await db.execute(
                select(CustomFieldValue).where(
                    CustomFieldValue.definition_id == d.id,
                    CustomFieldValue.record_id == record_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                CustomFieldValue(
                    definition_id=d.id,
                    record_id=record_id,
                    value=canonical,
                )
            )
        else:
            existing.value = canonical

    await db.flush()
    return await read_values(db, scope=scope, record_id=record_id)


async def _has_existing_value(db: AsyncSession, definition_id: uuid.UUID, record_id: uuid.UUID) -> bool:
    """Return True iff a non-empty value is already stored for this definition/record.

    A row whose stored ``value`` is NULL or an empty string is treated as
    missing so that required-field validation cannot be satisfied by an
    empty placeholder row left behind from a previous write.
    """
    row = (
        await db.execute(
            select(CustomFieldValue.value).where(
                CustomFieldValue.definition_id == definition_id,
                CustomFieldValue.record_id == record_id,
            )
        )
    ).first()
    if row is None:
        return False
    stored = row[0]
    return stored is not None and stored != ""


async def read_values(
    db: AsyncSession, *, scope: str, record_id: uuid.UUID
) -> dict[str, Any]:
    defs = await list_definitions(db, scope=scope, include_inactive=True)
    by_id = {d.id: d for d in defs}
    rows = (
        await db.execute(
            select(CustomFieldValue).where(
                CustomFieldValue.definition_id.in_(list(by_id.keys())),
                CustomFieldValue.record_id == record_id,
            )
        )
    ).scalars().all()
    out: dict[str, Any] = {
        by_id[r.definition_id].key: decode_value(by_id[r.definition_id].field_type, r.value)
        for r in rows
        if r.definition_id in by_id
    }
    # #326 P2: evaluate computed defs (no stored value, computed at read).
    for d in defs:
        if d.field_type != "computed":
            continue
        out[d.key] = await _evaluate_formula(db, scope=scope, record_id=record_id, formula=d.formula)
    return out


# ---------- #326 P2: computed-field evaluator ----------


def _scope_model(scope: str):
    """Lazy-import the ORM model class for a given scope. Lazy to avoid
    bootstrap-order coupling and to keep the registry trivially editable."""
    if scope == "customer":
        from app.models.customer import Customer
        return Customer
    if scope == "vendor":
        from app.models.vendor import Vendor
        return Vendor
    if scope == "product":
        from app.models.product import Product
        return Product
    if scope == "material":
        from app.models.material import Material
        return Material
    if scope == "supply":
        from app.models.supply import Supply
        return Supply
    if scope == "job":
        from app.models.job import Job
        return Job
    if scope == "sale":
        from app.models.sale import Sale
        return Sale
    if scope == "invoice":
        from app.models.invoice import Invoice
        return Invoice
    if scope == "quote":
        from app.models.quote import Quote
        return Quote
    if scope == "bill":
        from app.models.bill import Bill
        return Bill
    if scope == "sale_item":
        from app.models.sale_item import SaleItem
        return SaleItem
    if scope == "invoice_line":
        from app.models.invoice_line import InvoiceLine
        return InvoiceLine
    if scope == "quote_line":
        from app.models.quote import QuoteLine
        return QuoteLine
    if scope == "bill_line":
        from app.models.bill import BillLine
        return BillLine
    if scope == "purchase_order_line":
        from app.models.purchase_order import PurchaseOrderLine
        return PurchaseOrderLine
    if scope == "sales_order_line":
        from app.models.sales_order import SalesOrderLine
        return SalesOrderLine
    return None


async def _evaluate_formula(
    db: AsyncSession,
    *,
    scope: str,
    record_id: uuid.UUID,
    formula: str | None,
) -> Any:
    """Evaluate a computed-field formula on a specific record.

    Returns None when the formula is malformed, the scope has no
    registered ORM model, or the source column is missing on the row,
    rather than raising — a computed field is a display affordance and
    a transient evaluator error should never surface as an API failure
    on an otherwise valid record read.
    """
    if not formula:
        return None
    head, _, arg = formula.partition(":")
    if head not in COMPUTED_FORMULAS or not arg:
        return None
    Model = _scope_model(scope)
    if Model is None or not hasattr(Model, arg):
        return None
    if head == "days_since":
        from datetime import date

        row = (
            await db.execute(select(Model).where(Model.id == record_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        source = getattr(row, arg, None)
        if isinstance(source, datetime):
            source = source.date()
        if not isinstance(source, date):
            return None
        return (date.today() - source).days
    return None
