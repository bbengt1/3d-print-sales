"""#326 P2: multi_select + computed (days_since) + per-line scopes."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.custom_field import CustomFieldDefinition, CustomFieldValue
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.services.custom_field_service import (
    CustomFieldError,
    coerce_value,
    decode_value,
    read_values,
    upsert_values,
    validate_definition,
)


def test_multi_select_validation_requires_options():
    with pytest.raises(CustomFieldError):
        validate_definition(scope="customer", key="tags", field_type="multi_select", options=None)


def test_multi_select_coerce_and_decode_roundtrip():
    options = ["vip", "trade", "reseller"]
    stored = coerce_value("multi_select", ["vip", "reseller", "vip"], options)
    # Dedups while preserving order.
    decoded = decode_value("multi_select", stored)
    assert decoded == ["vip", "reseller"]


def test_multi_select_rejects_unknown_value():
    with pytest.raises(CustomFieldError):
        coerce_value("multi_select", ["vip", "bogus"], ["vip", "trade"])


def test_multi_select_accepts_comma_string():
    decoded = decode_value(
        "multi_select",
        coerce_value("multi_select", "vip, trade", ["vip", "trade"]),
    )
    assert decoded == ["vip", "trade"]


def test_computed_requires_formula():
    with pytest.raises(CustomFieldError):
        validate_definition(scope="invoice", key="days_open", field_type="computed", options=None)


def test_computed_rejects_unknown_formula_key():
    with pytest.raises(CustomFieldError):
        validate_definition(
            scope="invoice", key="x", field_type="computed", options=None, formula="bogus:foo"
        )


def test_computed_rejects_missing_argument():
    with pytest.raises(CustomFieldError):
        validate_definition(
            scope="invoice", key="x", field_type="computed", options=None, formula="days_since:"
        )


def test_computed_cannot_be_set_directly():
    with pytest.raises(CustomFieldError):
        coerce_value("computed", "5", None)


def test_per_line_scope_is_valid():
    # Should not raise — these scopes were added in #326 P2.
    for s in ("sale_item", "invoice_line", "quote_line", "bill_line"):
        validate_definition(scope=s, key="k", field_type="text", options=None)


@pytest.mark.asyncio
async def test_multi_select_round_trip_through_upsert(db_session):
    d = CustomFieldDefinition(
        scope="customer", key="segments", name="Segments",
        field_type="multi_select", options=["vip", "trade", "reseller"],
    )
    db_session.add(d)
    c = Customer(name="ACME")
    db_session.add(c)
    await db_session.flush()

    out = await upsert_values(
        db_session, scope="customer", record_id=c.id,
        values={"segments": ["vip", "reseller"]},
    )
    assert out["segments"] == ["vip", "reseller"]

    # Round-trip read.
    out2 = await read_values(db_session, scope="customer", record_id=c.id)
    assert out2["segments"] == ["vip", "reseller"]


@pytest.mark.asyncio
async def test_computed_days_since_invoice_date(db_session):
    d = CustomFieldDefinition(
        scope="invoice", key="days_open", name="Days Open",
        field_type="computed", formula="days_since:issue_date",
    )
    db_session.add(d)
    # Build a minimal invoice 7 days back.
    cust = Customer(name="Customer 1")
    db_session.add(cust)
    await db_session.flush()
    inv = Invoice(
        invoice_number="INV-1",
        customer_id=cust.id,
        issue_date=dt.date.today() - dt.timedelta(days=7),
        due_date=dt.date.today() + dt.timedelta(days=23),
        status="sent",
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total_due=Decimal("0"),
    )
    db_session.add(inv)
    await db_session.flush()

    out = await read_values(db_session, scope="invoice", record_id=inv.id)
    assert out["days_open"] == 7


@pytest.mark.asyncio
async def test_computed_silently_skipped_on_upsert(db_session):
    """An upsert payload that includes a computed-field key must not raise;
    it just gets ignored so generic record-save flows can pass through
    `{key: raw}` blindly.
    """
    d = CustomFieldDefinition(
        scope="invoice", key="days_open", name="Days Open",
        field_type="computed", formula="days_since:issue_date",
    )
    db_session.add(d)
    cust = Customer(name="Customer 2")
    db_session.add(cust)
    await db_session.flush()
    inv = Invoice(
        invoice_number="INV-2",
        customer_id=cust.id,
        issue_date=dt.date.today() - dt.timedelta(days=3),
        due_date=dt.date.today() + dt.timedelta(days=27),
        status="sent",
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total_due=Decimal("0"),
    )
    db_session.add(inv)
    await db_session.flush()

    out = await upsert_values(
        db_session, scope="invoice", record_id=inv.id,
        values={"days_open": 999},
    )
    # The computed value reflects the record, not the rejected write.
    assert out["days_open"] == 3
    # And no row should have been persisted for the computed def.
    cnt = (
        await db_session.execute(
            select(CustomFieldValue).where(CustomFieldValue.definition_id == d.id)
        )
    ).scalars().all()
    assert cnt == []


@pytest.mark.asyncio
async def test_per_line_custom_field_on_invoice_line(db_session):
    """Custom fields on the invoice_line scope key by InvoiceLine.id."""
    cust = Customer(name="LineCustomer")
    db_session.add(cust)
    await db_session.flush()
    inv = Invoice(
        invoice_number="INV-L1",
        customer_id=cust.id,
        issue_date=dt.date.today(),
        due_date=dt.date.today() + dt.timedelta(days=30),
        status="draft",
        subtotal=Decimal("10"),
        tax_amount=Decimal("0"),
        total_due=Decimal("10"),
    )
    db_session.add(inv)
    await db_session.flush()
    line = InvoiceLine(
        invoice_id=inv.id,
        description="Widget",
        quantity=1,
        unit_price=Decimal("10"),
        line_total=Decimal("10"),
    )
    db_session.add(line)
    await db_session.flush()

    d = CustomFieldDefinition(
        scope="invoice_line", key="warranty_months", name="Warranty (months)",
        field_type="number",
    )
    db_session.add(d)
    await db_session.flush()

    out = await upsert_values(
        db_session, scope="invoice_line", record_id=line.id,
        values={"warranty_months": "24"},
    )
    assert out["warranty_months"] == "24"
