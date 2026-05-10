"""#274 P1 (Codex review): creating a transfer with a non-existent
from_location_id / to_location_id must return a client error (404),
not surface as an uncaught Postgres IntegrityError -> 500.

The endpoint pre-validates the location IDs so the failure mode is
the same regardless of DB-level FK enforcement (SQLite tests do not
enforce FKs by default, but the bug surfaces in production on
Postgres).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.inventory_location import InventoryLocation
from app.models.material import Material


async def _location(db_session, name: str) -> InventoryLocation:
    loc = InventoryLocation(name=name)
    db_session.add(loc)
    await db_session.flush()
    return loc


async def _material(db_session) -> Material:
    m = Material(
        name="PLA",
        brand="Generic",
        spool_weight_g=1000,
        spool_price=Decimal("20"),
        net_usable_g=950,
        cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    return m


@pytest.mark.asyncio
async def test_create_transfer_unknown_from_location_returns_404(
    client: AsyncClient, auth_headers, db_session
):
    to_loc = await _location(db_session, "Showroom")
    mat = await _material(db_session)
    await db_session.commit()

    bogus = str(uuid.uuid4())
    r = await client.post(
        "/api/v1/inventory/transfers",
        headers=auth_headers,
        json={
            "from_location_id": bogus,
            "to_location_id": str(to_loc.id),
            "lines": [
                {"kind": "material", "material_id": str(mat.id), "quantity": "1"}
            ],
        },
    )
    assert r.status_code == 404, r.text
    assert "not found" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_transfer_unknown_to_location_returns_404(
    client: AsyncClient, auth_headers, db_session
):
    from_loc = await _location(db_session, "Workshop")
    mat = await _material(db_session)
    await db_session.commit()

    bogus = str(uuid.uuid4())
    r = await client.post(
        "/api/v1/inventory/transfers",
        headers=auth_headers,
        json={
            "from_location_id": str(from_loc.id),
            "to_location_id": bogus,
            "lines": [
                {"kind": "material", "material_id": str(mat.id), "quantity": "1"}
            ],
        },
    )
    assert r.status_code == 404, r.text
    assert "not found" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_transfer_both_locations_unknown_returns_404(
    client: AsyncClient, auth_headers, db_session
):
    mat = await _material(db_session)
    await db_session.commit()

    bogus_a = str(uuid.uuid4())
    bogus_b = str(uuid.uuid4())
    r = await client.post(
        "/api/v1/inventory/transfers",
        headers=auth_headers,
        json={
            "from_location_id": bogus_a,
            "to_location_id": bogus_b,
            "lines": [
                {"kind": "material", "material_id": str(mat.id), "quantity": "1"}
            ],
        },
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_create_transfer_valid_locations_still_succeeds(
    client: AsyncClient, auth_headers, db_session
):
    """Sanity check: pre-validation does not break the happy path."""
    from_loc = await _location(db_session, "Workshop")
    to_loc = await _location(db_session, "Showroom")
    mat = await _material(db_session)
    await db_session.commit()

    r = await client.post(
        "/api/v1/inventory/transfers",
        headers=auth_headers,
        json={
            "from_location_id": str(from_loc.id),
            "to_location_id": str(to_loc.id),
            "lines": [
                {"kind": "material", "material_id": str(mat.id), "quantity": "2"}
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["from_location_id"] == str(from_loc.id)
    assert body["to_location_id"] == str(to_loc.id)
