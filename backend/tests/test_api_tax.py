from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio

from app.models.sales_channel import SalesChannel
from app.services.accounting_service import seed_chart_of_accounts


@pytest_asyncio.fixture
async def seed_channel(db_session) -> SalesChannel:
    ch = SalesChannel(
        name="Etsy",
        platform_fee_pct=Decimal("6.5"),
        fixed_fee=Decimal("0.20"),
    )
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)
    return ch


async def _create_tax_profile(client, auth_headers, name="Texas Direct"):
    resp = await client.post(
        "/api/v1/tax/profiles",
        headers=auth_headers,
        json={
            "name": name,
            "jurisdiction": "TX",
            "tax_rate": "8.250",
            "filing_frequency": "monthly",
            "is_marketplace_facilitated": False,
            "is_active": True,
        },
    )
    return resp


def _sale_payload(channel_id=None, tax_profile_id=None, tax_treatment="seller_collected", tax_collected="1.48"):
    payload = {
        "date": "2026-03-23",
        "customer_name": "Tax Customer",
        "status": "paid",
        "tax_collected": tax_collected,
        "tax_treatment": tax_treatment,
        "items": [{"description": "Widget", "quantity": 1, "unit_price": 17.98, "unit_cost": 7.00}],
    }
    if channel_id:
        payload["channel_id"] = str(channel_id)
    if tax_profile_id:
        payload["tax_profile_id"] = str(tax_profile_id)
    return payload


@pytest.mark.asyncio
async def test_tax_liability_report_seller_vs_marketplace(client, auth_headers, seed_channel, db_session):
    await seed_chart_of_accounts(db_session)
    direct_profile = (await _create_tax_profile(client, auth_headers, "Texas Direct")).json()
    marketplace_profile = (await client.post(
        "/api/v1/tax/profiles",
        headers=auth_headers,
        json={
            "name": "Etsy Marketplace",
            "jurisdiction": "TX",
            "tax_rate": "8.250",
            "filing_frequency": "monthly",
            "is_marketplace_facilitated": True,
            "is_active": True,
        },
    )).json()

    direct_sale = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload(tax_profile_id=direct_profile["id"], tax_treatment="seller_collected", tax_collected="1.48"))
    assert direct_sale.status_code == 201

    market_sale = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload(channel_id=seed_channel.id, tax_profile_id=marketplace_profile["id"], tax_treatment="marketplace_facilitated", tax_collected="2.10"))
    assert market_sale.status_code == 201

    remittance = await client.post(
        "/api/v1/tax/remittances",
        headers=auth_headers,
        json={
            "tax_profile_id": direct_profile["id"],
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "remittance_date": "2026-04-20",
            "amount": "1.00",
            "reference_number": "TX-MAR-1",
        },
    )
    assert remittance.status_code == 201

    report = await client.get("/api/v1/tax/reports/liability", headers=auth_headers)
    assert report.status_code == 200
    data = report.json()
    assert float(data["total_seller_collected"]) == 1.48
    assert float(data["total_marketplace_facilitated"]) == 2.10
    assert float(data["total_remitted"]) == 1.00
    assert float(data["total_outstanding_liability"]) == 0.48


@pytest.mark.asyncio
async def test_sale_response_exposes_tax_treatment(client, auth_headers, db_session):
    await seed_chart_of_accounts(db_session)
    profile = (await _create_tax_profile(client, auth_headers)).json()
    resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload(tax_profile_id=profile["id"], tax_treatment="seller_collected"))
    assert resp.status_code == 201
    assert resp.json()["tax_profile_id"] == profile["id"]
    assert resp.json()["tax_treatment"] == "seller_collected"
