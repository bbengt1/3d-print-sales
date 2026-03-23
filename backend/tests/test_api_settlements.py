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


def _sale_payload(channel_id, tax_treatment="marketplace_facilitated"):
    return {
        "date": "2026-03-23",
        "customer_name": "Marketplace Buyer",
        "channel_id": str(channel_id),
        "status": "paid",
        "tax_collected": "1.50",
        "tax_treatment": tax_treatment,
        "shipping_cost": "3.00",
        "shipping_charged": "4.00",
        "items": [{"description": "Marketplace Widget", "quantity": 1, "unit_price": 20.00, "unit_cost": 7.00}],
    }


@pytest.mark.asyncio
async def test_create_settlement_and_reconcile_discrepancy(client, auth_headers, seed_channel, db_session):
    await seed_chart_of_accounts(db_session)
    sale_resp = await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload(seed_channel.id))
    assert sale_resp.status_code == 201
    sale = sale_resp.json()

    settlement_resp = await client.post(
        "/api/v1/settlements",
        headers=auth_headers,
        json={
            "settlement_number": "ESTY-2026-03-A",
            "channel_id": str(seed_channel.id),
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "payout_date": "2026-04-02",
            "adjustments": "-1.00",
            "reserves_held": "2.00",
            "net_deposit": "18.13",
            "lines": [
                {"sale_id": sale["id"], "line_type": "sale", "description": sale["sale_number"], "amount": "25.50"},
                {"line_type": "fee", "description": "Marketplace fee", "amount": "-1.37"},
                {"line_type": "reserve", "description": "Reserve hold", "amount": "-2.00"}
            ]
        },
    )
    assert settlement_resp.status_code == 201
    settlement = settlement_resp.json()
    assert len(settlement["lines"]) == 3
    assert float(settlement["expected_net"]) == 21.13
    assert float(settlement["discrepancy_amount"]) == -3.0


@pytest.mark.asyncio
async def test_settlement_reconciliation_report(client, auth_headers, seed_channel, db_session):
    await seed_chart_of_accounts(db_session)
    await client.post("/api/v1/sales", headers=auth_headers, json=_sale_payload(seed_channel.id))
    await client.post(
        "/api/v1/settlements",
        headers=auth_headers,
        json={
            "settlement_number": "ESTY-2026-03-B",
            "channel_id": str(seed_channel.id),
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "payout_date": "2026-04-03",
            "adjustments": "0.00",
            "reserves_held": "1.00",
            "net_deposit": "20.13",
        },
    )

    report = await client.get("/api/v1/settlements/reports/reconciliation", headers=auth_headers)
    assert report.status_code == 200
    data = report.json()
    assert len(data["rows"]) >= 1
    assert float(data["total_net_deposit"]) >= 20.13
