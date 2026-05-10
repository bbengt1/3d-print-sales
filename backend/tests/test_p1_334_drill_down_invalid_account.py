"""#334 P1 (Codex): account drill-down with a non-existent account_id must
return a 404 client error instead of a 500 from an unhandled ValueError.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_account_drill_down_missing_account_returns_404(
    client: AsyncClient, auth_headers
):
    bogus_account_id = uuid.uuid4()
    r = await client.get(
        "/api/v1/reports/account-drill-down",
        params={"account_id": str(bogus_account_id)},
        headers=auth_headers,
    )
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert str(bogus_account_id) in detail
