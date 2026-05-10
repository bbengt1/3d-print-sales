from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.tax_profile import TaxProfile, TaxProfileComponent


@pytest.mark.asyncio
async def test_compute_single_rate(client: AsyncClient, auth_headers, db_session):
    p = TaxProfile(name="WA 7%", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add(p)
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/tax/compute?profile_id={p.id}&subtotal=100",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tax"] == "7.00"
    assert len(body["components"]) == 1
    assert body["is_reverse_charge"] is False


@pytest.mark.asyncio
async def test_compute_compound(client: AsyncClient, auth_headers, db_session):
    p = TaxProfile(name="QC compound", jurisdiction="QC", tax_rate=Decimal("0"), is_compound=True)
    db_session.add(p)
    await db_session.flush()
    db_session.add(TaxProfileComponent(profile_id=p.id, name="GST", rate=Decimal("5.000"), apply_order=0))
    db_session.add(TaxProfileComponent(profile_id=p.id, name="QST", rate=Decimal("9.975"), apply_order=1))
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/tax/compute?profile_id={p.id}&subtotal=100",
        headers=auth_headers,
    )
    body = resp.json()
    assert len(body["components"]) == 2
    assert body["components"][0]["amount"] == "5.00"
    assert body["components"][1]["amount"] == "10.47"


@pytest.mark.asyncio
async def test_compute_reverse_charge_flag(client: AsyncClient, auth_headers, db_session):
    p = TaxProfile(name="EU rev", jurisdiction="EU", tax_rate=Decimal("20.000"), is_reverse_charge=True)
    db_session.add(p)
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/tax/compute?profile_id={p.id}&subtotal=100",
        headers=auth_headers,
    )
    assert resp.json()["is_reverse_charge"] is True


@pytest.mark.asyncio
async def test_compute_unknown_profile_404(client: AsyncClient, auth_headers):
    import uuid
    resp = await client.post(
        f"/api/v1/tax/compute?profile_id={uuid.uuid4()}&subtotal=100",
        headers=auth_headers,
    )
    assert resp.status_code == 404
