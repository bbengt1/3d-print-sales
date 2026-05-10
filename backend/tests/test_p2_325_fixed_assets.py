"""#325 P2: fixed-assets bulk CSV import + post-monthly-due cron entry."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.fixed_asset import FixedAsset


async def _seed_coa(db_session):
    for code, name, kind, side in [
        ("1700", "Equipment", "asset", "debit"),
        ("1750", "Accumulated Depreciation", "asset", "credit"),
        ("6700", "Depreciation Expense", "expense", "debit"),
    ]:
        existing = (await db_session.execute(select(Account).where(Account.code == code))).scalar_one_or_none()
        if existing is None:
            db_session.add(Account(code=code, name=name, account_type=kind, normal_balance=side))
    await db_session.flush()


@pytest.mark.asyncio
async def test_bulk_import_creates_assets(client: AsyncClient, auth_headers, db_session):
    await _seed_coa(db_session)
    await db_session.commit()
    csv_bytes = (
        "name,acquired_on,acquisition_cost,useful_life_months,salvage_value,depreciation_method\n"
        "Printer A,2026-01-15,4500,60,500,straight_line\n"
        "Printer B,2026-02-01,2000,36,0,straight_line\n"
    ).encode()
    r = await client.post(
        "/api/v1/fixed-assets/bulk-import.csv",
        files={"file": ("assets.csv", csv_bytes, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["imported"] == 2
    rows = (await db_session.execute(select(FixedAsset))).scalars().all()
    names = {a.name for a in rows}
    assert {"Printer A", "Printer B"} <= names


@pytest.mark.asyncio
async def test_bulk_import_per_row_errors(client: AsyncClient, auth_headers, db_session):
    await _seed_coa(db_session)
    await db_session.commit()
    csv_bytes = (
        "name,acquired_on,acquisition_cost,useful_life_months\n"
        "Good,2026-01-01,1000,12\n"
        "Bad,not-a-date,1000,12\n"
    ).encode()
    r = await client.post(
        "/api/v1/fixed-assets/bulk-import.csv",
        files={"file": ("a.csv", csv_bytes, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 1
    bad_row = next(x for x in body["rows"] if x.get("error"))
    assert bad_row["row"] == 3


@pytest.mark.asyncio
async def test_bulk_import_missing_columns_400(client: AsyncClient, auth_headers, db_session):
    await _seed_coa(db_session)
    await db_session.commit()
    csv_bytes = b"name,foo\nA,1\n"
    r = await client.post(
        "/api/v1/fixed-assets/bulk-import.csv",
        files={"file": ("a.csv", csv_bytes, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_post_monthly_due_runs(client: AsyncClient, auth_headers, db_session):
    """Smoke: endpoint runs without error even when no assets are due."""
    r = await client.post("/api/v1/fixed-assets/post-monthly-due", headers=auth_headers)
    assert r.status_code == 200
    assert "through" in r.json()
