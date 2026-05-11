"""#328 P2 final bullet: Job → Project rollup link."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.division import Project
from app.models.job import Job
from app.models.material import Material


@pytest.mark.asyncio
async def test_job_create_persists_project_id(client: AsyncClient, auth_headers, db_session):
    mat = Material(
        name="PLA", brand="X", spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"), net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.02"),
    )
    db_session.add(mat)
    project = Project(name="Holiday Campaign")
    db_session.add(project)
    await db_session.commit()

    r = await client.post(
        "/api/v1/jobs",
        json={
            "date": "2026-05-11",
            "product_name": "Widget",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(mat.id),
            "material_per_plate_g": "10",
            "print_time_per_plate_hrs": "1",
            "project_id": str(project.id),
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["project_id"] == str(project.id)

    row = (
        await db_session.execute(select(Job).where(Job.id == uuid.UUID(r.json()["id"])))
    ).scalar_one()
    assert row.project_id == project.id


@pytest.mark.asyncio
async def test_job_update_can_clear_project(client: AsyncClient, auth_headers, db_session):
    mat = Material(
        name="PLA", brand="X", spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"), net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.02"),
    )
    project = Project(name="P1")
    db_session.add_all([mat, project])
    await db_session.commit()

    create = await client.post(
        "/api/v1/jobs",
        json={
            "date": "2026-05-11",
            "product_name": "Widget",
            "qty_per_plate": 1,
            "num_plates": 1,
            "material_id": str(mat.id),
            "material_per_plate_g": "10",
            "print_time_per_plate_hrs": "1",
            "project_id": str(project.id),
        },
        headers=auth_headers,
    )
    job_id = create.json()["id"]

    cleared = await client.put(
        f"/api/v1/jobs/{job_id}",
        json={"project_id": None},
        headers=auth_headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["project_id"] is None
