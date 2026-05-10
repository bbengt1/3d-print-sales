"""#229: auto job creation from watch-directory discovery."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.job import Job
from app.models.job_discovery import JobDiscoveryCandidate, JobDiscoverySource
from app.models.material import Material
from app.services.job_discovery_service import (
    JobDiscoveryError,
    promote_candidate,
    reject_candidate,
    scan_source,
)


async def _source(db_session, path: Path) -> JobDiscoverySource:
    s = JobDiscoverySource(
        name=f"src-{path.name}",
        kind="watch_directory",
        path=str(path),
        is_active=True,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.asyncio
async def test_scan_picks_up_gcode_files(db_session, tmp_path: Path):
    (tmp_path / "model_a.gcode").write_text("G1 X10 Y10\n")
    (tmp_path / "model_b.3mf").write_bytes(b"PK\x03\x04dummy")
    (tmp_path / "ignore.txt").write_text("ignore")
    src = await _source(db_session, tmp_path)
    await db_session.commit()

    summary = await scan_source(db_session, source_id=src.id)
    assert summary["discovered"] == 2
    assert summary["skipped_duplicates"] == 0
    rows = (await db_session.execute(select(JobDiscoveryCandidate))).scalars().all()
    names = {r.source_filename for r in rows}
    assert {"model_a.gcode", "model_b.3mf"} <= names


@pytest.mark.asyncio
async def test_rescan_dedupes(db_session, tmp_path: Path):
    (tmp_path / "x.gcode").write_text("G1\n")
    src = await _source(db_session, tmp_path)
    await db_session.commit()
    s1 = await scan_source(db_session, source_id=src.id)
    await db_session.commit()
    s2 = await scan_source(db_session, source_id=src.id)
    assert s1["discovered"] == 1
    assert s2["discovered"] == 0
    assert s2["skipped_duplicates"] == 1


@pytest.mark.asyncio
async def test_scan_walks_subdirs_skips_hidden(db_session, tmp_path: Path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.gcode").write_text("G1\n")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "skipped.gcode").write_text("G1\n")
    src = await _source(db_session, tmp_path)
    await db_session.commit()
    summary = await scan_source(db_session, source_id=src.id)
    assert summary["discovered"] == 1


@pytest.mark.asyncio
async def test_inactive_source_refuses(db_session, tmp_path: Path):
    src = await _source(db_session, tmp_path)
    src.is_active = False
    await db_session.commit()
    with pytest.raises(JobDiscoveryError):
        await scan_source(db_session, source_id=src.id)


@pytest.mark.asyncio
async def test_missing_path_raises(db_session, tmp_path: Path):
    src = await _source(db_session, tmp_path / "does_not_exist")
    await db_session.commit()
    with pytest.raises(JobDiscoveryError):
        await scan_source(db_session, source_id=src.id)


@pytest.mark.asyncio
async def test_promote_creates_draft_job(db_session, tmp_path: Path):
    m = Material(
        name="PLA", brand="Generic",
        spool_weight_g=Decimal("1000"), spool_price=Decimal("20"),
        net_usable_g=Decimal("950"), cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    (tmp_path / "model.gcode").write_text("G1\n")
    src = await _source(db_session, tmp_path)
    await db_session.commit()
    await scan_source(db_session, source_id=src.id)
    cand = (await db_session.execute(select(JobDiscoveryCandidate))).scalar_one()
    cand_id = cand.id
    m_id = m.id
    await db_session.commit()

    promoted = await promote_candidate(
        db_session,
        candidate_id=cand_id,
        job_payload={
            "product_name": "Widget",
            "qty_per_plate": 4,
            "num_plates": 2,
            "material_id": m_id,
            "material_per_plate_g": Decimal("50"),
            "print_time_per_plate_hrs": Decimal("2.5"),
        },
    )
    assert promoted.status == "promoted"
    assert promoted.promoted_job_id is not None
    job = (await db_session.execute(select(Job).where(Job.id == promoted.promoted_job_id))).scalar_one()
    assert job.status == "draft"
    assert job.product_name == "Widget"
    assert job.total_pieces == 8


@pytest.mark.asyncio
async def test_promote_missing_fields_raises(db_session, tmp_path: Path):
    (tmp_path / "x.gcode").write_text("G1\n")
    src = await _source(db_session, tmp_path)
    await db_session.commit()
    await scan_source(db_session, source_id=src.id)
    cand = (await db_session.execute(select(JobDiscoveryCandidate))).scalar_one()
    with pytest.raises(JobDiscoveryError, match="Missing job fields"):
        await promote_candidate(
            db_session, candidate_id=cand.id, job_payload={"product_name": "x"},
        )


@pytest.mark.asyncio
async def test_reject_marks_status(db_session, tmp_path: Path):
    (tmp_path / "x.gcode").write_text("G1\n")
    src = await _source(db_session, tmp_path)
    await db_session.commit()
    await scan_source(db_session, source_id=src.id)
    cand = (await db_session.execute(select(JobDiscoveryCandidate))).scalar_one()
    rejected = await reject_candidate(
        db_session, candidate_id=cand.id, reason="not a real print"
    )
    assert rejected.status == "rejected"
    assert "not a real print" in (rejected.parse_warnings or "")


@pytest.mark.asyncio
async def test_promote_already_promoted_refuses(db_session, tmp_path: Path):
    m = Material(
        name="PLA", brand="Generic",
        spool_weight_g=Decimal("1000"), spool_price=Decimal("20"),
        net_usable_g=Decimal("950"), cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    (tmp_path / "x.gcode").write_text("G1\n")
    src = await _source(db_session, tmp_path)
    await db_session.commit()
    await scan_source(db_session, source_id=src.id)
    cand = (await db_session.execute(select(JobDiscoveryCandidate))).scalar_one()
    payload = {
        "product_name": "X", "qty_per_plate": 1, "num_plates": 1,
        "material_id": m.id,
        "material_per_plate_g": Decimal("10"),
        "print_time_per_plate_hrs": Decimal("1"),
    }
    await promote_candidate(db_session, candidate_id=cand.id, job_payload=payload)
    with pytest.raises(JobDiscoveryError, match="status promoted"):
        await promote_candidate(db_session, candidate_id=cand.id, job_payload=payload)
