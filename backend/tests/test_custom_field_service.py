from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from app.services.custom_field_service import (
    CustomFieldError,
    coerce_value,
    decode_value,
    list_definitions,
    read_values,
    upsert_values,
    validate_definition,
)


# ---------- validate_definition ----------


def test_validate_unknown_scope():
    with pytest.raises(CustomFieldError):
        validate_definition(scope="bogus", key="x", field_type="text", options=None)


def test_validate_invalid_key():
    with pytest.raises(CustomFieldError):
        validate_definition(scope="customer", key="Bad-Key", field_type="text", options=None)


def test_validate_unknown_type():
    with pytest.raises(CustomFieldError):
        validate_definition(scope="customer", key="x", field_type="bogus", options=None)


def test_validate_dropdown_requires_options():
    with pytest.raises(CustomFieldError):
        validate_definition(scope="customer", key="x", field_type="dropdown", options=None)


# ---------- coerce_value ----------


def test_coerce_text():
    assert coerce_value("text", "hello", None) == "hello"


def test_coerce_number_invalid():
    with pytest.raises(CustomFieldError):
        coerce_value("number", "not a number", None)


def test_coerce_number_valid():
    assert coerce_value("number", "12.34", None) == "12.34"


def test_coerce_date_iso():
    assert coerce_value("date", "2026-05-01", None) == "2026-05-01"


def test_coerce_date_invalid():
    with pytest.raises(CustomFieldError):
        coerce_value("date", "not a date", None)


def test_coerce_checkbox_truthy():
    assert coerce_value("checkbox", True, None) == "true"
    assert coerce_value("checkbox", "yes", None) == "true"
    assert coerce_value("checkbox", "0", None) == "false"


def test_coerce_dropdown_must_match():
    assert coerce_value("dropdown", "small", ["small", "medium", "large"]) == "small"
    with pytest.raises(CustomFieldError):
        coerce_value("dropdown", "huge", ["small", "medium", "large"])


def test_decode_checkbox_round_trip():
    assert decode_value("checkbox", "true") is True
    assert decode_value("checkbox", "false") is False


# ---------- service ----------


@pytest.mark.asyncio
async def test_list_definitions_unknown_scope_rejected(db_session):
    with pytest.raises(CustomFieldError):
        await list_definitions(db_session, scope="bogus")


@pytest.mark.asyncio
async def test_upsert_and_read_text_field(db_session):
    from app.models.custom_field import CustomFieldDefinition

    d = CustomFieldDefinition(
        scope="customer", key="preferred_color", name="Preferred filament color",
        field_type="text", is_required=False,
    )
    db_session.add(d)
    await db_session.flush()

    rec_id = uuid.uuid4()
    out = await upsert_values(
        db_session,
        scope="customer",
        record_id=rec_id,
        values={"preferred_color": "Bambu Beige"},
    )
    assert out == {"preferred_color": "Bambu Beige"}

    # Re-upsert overwrites
    out = await upsert_values(
        db_session,
        scope="customer",
        record_id=rec_id,
        values={"preferred_color": "Forest Green"},
    )
    assert out == {"preferred_color": "Forest Green"}

    again = await read_values(db_session, scope="customer", record_id=rec_id)
    assert again == {"preferred_color": "Forest Green"}


@pytest.mark.asyncio
async def test_required_field_missing_raises(db_session):
    from app.models.custom_field import CustomFieldDefinition

    d = CustomFieldDefinition(
        scope="customer", key="reqfield", name="Required",
        field_type="text", is_required=True,
    )
    db_session.add(d)
    await db_session.flush()

    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=uuid.uuid4(),
            values={},  # required field missing
        )


@pytest.mark.asyncio
async def test_unknown_key_silently_ignored(db_session):
    """Sending values with keys not defined for the scope is a no-op,
    not an error — keeps the API loose for callers that send a superset.
    """
    rec_id = uuid.uuid4()
    out = await upsert_values(
        db_session,
        scope="customer",
        record_id=rec_id,
        values={"undefined_key": "anything"},
    )
    assert out == {}
