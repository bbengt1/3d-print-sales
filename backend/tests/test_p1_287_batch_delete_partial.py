"""Regression test for issue #287 P1 (Codex review on PR #287).

Earlier `batch_delete` called `await db.rollback()` inside the per-row
loop. When the 2nd of 3 rows hit a FK `IntegrityError`, the rollback
discarded the 1st row's already-flushed delete even though `deleted`
had been incremented for it. The reported success count was right but
the database state didn't match — a misleading partial-success.

The fix wraps each per-row delete in a SAVEPOINT
(`async with db.begin_nested():`). On IntegrityError the savepoint
rolls back ONLY that row; earlier successful deletes survive and the
final count matches reality.

This test creates 3 vendors, makes the middle one fail on delete by
hooking a `before_delete` event that raises StatementError wrapping an
IntegrityError, and asserts:

    - deleted == 2
    - vendors[0] and vendors[2] are gone from the DB
    - vendors[1] (the failing one) is still present
"""

from __future__ import annotations

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.models.vendor import Vendor
from app.services.batch_ops_service import batch_delete


@pytest.mark.asyncio
async def test_batch_delete_partial_success_isolated_with_savepoints(db_session):
    vendors = [Vendor(name=f"P1-287-{i}") for i in range(3)]
    for v in vendors:
        db_session.add(v)
    await db_session.flush()
    ids = [v.id for v in vendors]
    fail_id = ids[1]

    # Simulate an FK constraint blocking the middle vendor's delete.
    # We hook the mapper before_delete event and raise an IntegrityError
    # for that specific row. SQLAlchemy will surface it from flush()
    # exactly like a real FK violation would.
    def block_middle_delete(mapper, connection, target):  # noqa: ARG001
        if target.id == fail_id:
            raise IntegrityError(
                statement="DELETE FROM vendors",
                params={},
                orig=Exception("simulated FK constraint"),
            )

    event.listen(Vendor, "before_delete", block_middle_delete)
    try:
        out = await batch_delete(db_session, scope="vendor", ids=ids)
    finally:
        event.remove(Vendor, "before_delete", block_middle_delete)

    # Reported counts.
    assert out["deleted"] == 2, out
    assert len(out["errors"]) == 1, out
    assert out["errors"][0]["id"] == str(fail_id)

    # Database state must match the reported counts: the savepoint
    # rollback should have only discarded the failing row's delete.
    # Earlier and later successful deletes must persist.
    remaining = (
        await db_session.execute(select(Vendor.id).where(Vendor.id.in_(ids)))
    ).scalars().all()
    assert remaining == [fail_id], (
        f"Expected only the failing vendor ({fail_id}) to remain; got {remaining}"
    )
