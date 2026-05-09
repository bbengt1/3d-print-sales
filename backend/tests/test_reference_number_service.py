from __future__ import annotations

import pytest

from app.services.reference_number_service import (
    FORMATS,
    format_reference_number,
    next_number,
    parse_reference_number,
)


@pytest.mark.asyncio
async def test_next_number_allocates_first_value(db_session):
    n = await next_number(db_session, "sale", year=2026)
    assert n == "S-2026-0001"


@pytest.mark.asyncio
async def test_next_number_increments_within_year(db_session):
    a = await next_number(db_session, "sale", year=2026)
    b = await next_number(db_session, "sale", year=2026)
    c = await next_number(db_session, "sale", year=2026)
    assert (a, b, c) == ("S-2026-0001", "S-2026-0002", "S-2026-0003")


@pytest.mark.asyncio
async def test_next_number_resets_per_year(db_session):
    a26 = await next_number(db_session, "sale", year=2026)
    a27 = await next_number(db_session, "sale", year=2027)
    b26 = await next_number(db_session, "sale", year=2026)
    assert a26 == "S-2026-0001"
    assert a27 == "S-2027-0001"
    assert b26 == "S-2026-0002"


@pytest.mark.asyncio
async def test_next_number_separates_scopes(db_session):
    s = await next_number(db_session, "sale", year=2026)
    i = await next_number(db_session, "invoice", year=2026)
    q = await next_number(db_session, "quote", year=2026)
    assert s == "S-2026-0001"
    assert i == "INV-2026-0001"
    assert q == "Q-2026-0001"


@pytest.mark.asyncio
async def test_next_number_unknown_scope_raises(db_session):
    with pytest.raises(KeyError):
        await next_number(db_session, "not_a_scope", year=2026)


def test_format_reference_number_unknown_scope_raises():
    with pytest.raises(KeyError):
        format_reference_number("not_a_scope", 2026, 1)


def test_parse_reference_number_canonical_round_trip():
    for scope in ("sale", "invoice", "quote"):
        formatted = format_reference_number(scope, 2026, 42)
        parsed = parse_reference_number(scope, formatted)
        assert parsed == (2026, 42)


def test_parse_reference_number_returns_none_for_non_canonical():
    assert parse_reference_number("invoice", "CUST-PROJECT-7") is None
    assert parse_reference_number("sale", "garbage") is None
    assert parse_reference_number("not_a_scope", "anything") is None


def test_formats_registry_has_all_expected_scopes():
    # If a future issue adds a scope, add it here too. Failing this test on
    # purpose forces the registration check.
    assert set(FORMATS.keys()) >= {"sale", "invoice", "quote"}
