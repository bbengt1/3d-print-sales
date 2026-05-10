"""#230: filament resolve_or_catalog."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.material import Material
from app.services.filament_resolver import resolve_or_catalog


async def _seed_material(
    db_session, name="PLA Black", brand="Generic", spool_id=None
) -> Material:
    m = Material(
        name=name, brand=brand,
        spool_weight_g=Decimal("1000"), spool_price=Decimal("20"),
        net_usable_g=Decimal("950"), cost_per_g=Decimal("0.02"),
        discovery_metadata={"spool_id": spool_id} if spool_id else None,
    )
    db_session.add(m)
    await db_session.flush()
    return m


@pytest.mark.asyncio
async def test_exact_brand_and_name_matches_existing(db_session):
    m = await _seed_material(db_session, "PLA Black", "Generic")
    await db_session.commit()
    res = await resolve_or_catalog(
        db_session, name="PLA Black", brand="Generic", source="print_job",
    )
    assert res["created"] is False
    assert res["material_id"] == str(m.id)
    assert res["matched_via"] == "brand_and_name"


@pytest.mark.asyncio
async def test_case_insensitive_match(db_session):
    m = await _seed_material(db_session, "PLA Black", "Generic")
    await db_session.commit()
    res = await resolve_or_catalog(
        db_session, name="pla black", brand="GENERIC", source="print_job",
    )
    assert res["created"] is False
    assert res["material_id"] == str(m.id)


@pytest.mark.asyncio
async def test_missing_creates_new_with_review_flag(db_session):
    res = await resolve_or_catalog(
        db_session, name="PLA Bone White", brand="Polymaker",
        source="slicer_metadata", source_job_id="job-123",
    )
    assert res["created"] is True
    assert res["needs_review"] is True
    new_mat = (
        await db_session.execute(select(Material).where(Material.id == uuid.UUID(res["material_id"])))
    ).scalar_one()
    assert new_mat.discovered_via == "slicer_metadata"
    assert new_mat.discovery_metadata["job_id"] == "job-123"
    assert new_mat.needs_review is True


@pytest.mark.asyncio
async def test_complete_pricing_doesnt_flag_review(db_session):
    res = await resolve_or_catalog(
        db_session, name="PETG Red", brand="Bambu",
        source="csv_import",
        spool_weight_g=Decimal("1000"),
        spool_price=Decimal("25"),
        net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.026"),
    )
    assert res["created"] is True
    assert res["needs_review"] is False
    new_mat = (
        await db_session.execute(select(Material).where(Material.id == uuid.UUID(res["material_id"])))
    ).scalar_one()
    assert new_mat.cost_per_g == Decimal("0.026000")


@pytest.mark.asyncio
async def test_spool_id_takes_priority_over_brand_match(db_session):
    # Two materials sharing name; one with a spool_id stored in metadata.
    sticky = await _seed_material(db_session, "PLA Black", "BrandA", spool_id="S-001")
    other = await _seed_material(db_session, "PLA Black", "BrandB")
    await db_session.commit()
    # Source reports brand=BrandB but the spool_id matches BrandA's record.
    res = await resolve_or_catalog(
        db_session, name="PLA Black", brand="BrandB", spool_id="S-001",
        source="printer_telemetry",
    )
    assert res["created"] is False
    assert res["material_id"] == str(sticky.id)
    assert res["matched_via"] == "spool_id"


@pytest.mark.asyncio
async def test_endpoint_round_trip(client: AsyncClient, auth_headers, db_session):
    r = await client.post(
        "/api/v1/materials/resolve-from-print",
        json={
            "name": "ABS Blue",
            "brand": "Generic",
            "color": "#0044ff",
            "source": "print_job",
            "source_job_id": "job-xyz",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["needs_review"] is True
    # Re-resolving should match the same record now
    r2 = await client.post(
        "/api/v1/materials/resolve-from-print",
        json={"name": "ABS Blue", "brand": "Generic", "source": "print_job"},
        headers=auth_headers,
    )
    assert r2.json()["created"] is False
    assert r2.json()["material_id"] == body["material_id"]


@pytest.mark.asyncio
async def test_unknown_source_400(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/v1/materials/resolve-from-print",
        json={"name": "X", "source": "made_up_source"},
        headers=auth_headers,
    )
    assert r.status_code == 400
