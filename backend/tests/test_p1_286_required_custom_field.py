"""Regression for Codex P1 review on PR #286.

The required-field guard previously only checked whether the key was
present in the submitted payload (or whether any row existed for the
record), which let callers satisfy a required field with ``None`` /
empty-string / empty-list values. ``coerce_value`` would then store
``None``, leaving the supposedly required field empty.

This test locks in the stricter behavior:

* missing key without prior data --> rejected
* explicit ``None`` --> rejected
* explicit empty string --> rejected
* explicit empty list --> rejected (defensive; covers any future
  list-shaped field types)
* a required field cannot later be cleared to empty
* a non-empty value continues to round-trip successfully
"""

from __future__ import annotations

import uuid

import pytest

from app.models.custom_field import CustomFieldDefinition
from app.services.custom_field_service import (
    CustomFieldError,
    upsert_values,
    read_values,
)


async def _make_required_text(db_session) -> CustomFieldDefinition:
    d = CustomFieldDefinition(
        scope="customer",
        key="account_manager",
        name="Account manager",
        field_type="text",
        is_required=True,
    )
    db_session.add(d)
    await db_session.flush()
    return d


@pytest.mark.asyncio
async def test_required_field_rejects_missing_key(db_session):
    await _make_required_text(db_session)
    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=uuid.uuid4(),
            values={},
        )


@pytest.mark.asyncio
async def test_required_field_rejects_none(db_session):
    await _make_required_text(db_session)
    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=uuid.uuid4(),
            values={"account_manager": None},
        )


@pytest.mark.asyncio
async def test_required_field_rejects_empty_string(db_session):
    await _make_required_text(db_session)
    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=uuid.uuid4(),
            values={"account_manager": ""},
        )


@pytest.mark.asyncio
async def test_required_field_rejects_empty_list(db_session):
    """Defensive: list-shaped values must also be rejected as empty.

    Even though current ``FIELD_TYPES`` are scalar, the guard should not
    accept ``[]`` as a satisfying value for a required field — that
    avoids regressing the constraint when list-style types
    (multi-select) are added.
    """
    await _make_required_text(db_session)
    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=uuid.uuid4(),
            values={"account_manager": []},
        )


@pytest.mark.asyncio
async def test_required_field_accepts_non_empty(db_session):
    await _make_required_text(db_session)
    rec_id = uuid.uuid4()
    out = await upsert_values(
        db_session,
        scope="customer",
        record_id=rec_id,
        values={"account_manager": "Alice"},
    )
    assert out == {"account_manager": "Alice"}

    again = await read_values(db_session, scope="customer", record_id=rec_id)
    assert again == {"account_manager": "Alice"}


@pytest.mark.asyncio
async def test_required_field_cannot_be_cleared_to_empty(db_session):
    """Once set, a required field must not be clearable via "" / None."""
    await _make_required_text(db_session)
    rec_id = uuid.uuid4()

    # Initial valid value
    await upsert_values(
        db_session,
        scope="customer",
        record_id=rec_id,
        values={"account_manager": "Alice"},
    )

    # Try to clear with empty string
    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=rec_id,
            values={"account_manager": ""},
        )

    # Try to clear with None
    with pytest.raises(CustomFieldError):
        await upsert_values(
            db_session,
            scope="customer",
            record_id=rec_id,
            values={"account_manager": None},
        )

    # Original value is still intact
    again = await read_values(db_session, scope="customer", record_id=rec_id)
    assert again == {"account_manager": "Alice"}
