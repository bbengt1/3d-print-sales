"""Codex P1 on PR #281: load active rules once per import pass.

Before the fix, `apply_rules_to_import` called `evaluate_rules_for_line`
for every unmatched line, and that function executed a fresh
`SELECT StatementMatchRule WHERE is_active` each time — N+1 against the
rule table on every statement upload / manual re-apply.

The fix hoists the rule fetch into a single `_load_active_rules` call at
the top of `apply_rules_to_import` (and `preview_rules_for_import`),
passing the cached list down. This regression test wraps that helper and
asserts it executes exactly once per pass, regardless of how many
unmatched lines an import contains.
"""

from __future__ import annotations

import pytest

from app.models.account import Account
from app.models.statement_match_rule import StatementMatchRule
from app.services import statement_match_rule_service as svc
from app.services.statement_import_service import import_statement


# Three unmatched lines so a regression (per-line SELECT) would surface as
# 3 calls vs the expected 1.
SAMPLE_CSV = """Date,Amount,Description,FITID
2026-05-01,-25.00,Filament supplier,FITID001
2026-05-02,-12.50,Filament other supplier,FITID002
2026-05-03,500.00,Etsy payout,FITID003
"""


async def _bank(db_session, code="1010", name="Operating"):
    a = Account(
        code=code, name=name, account_type="asset", normal_balance="debit",
        is_bank_account=True, bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_apply_rules_to_import_loads_rules_once(db_session, monkeypatch):
    bank = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="csv",
        source_filename="x.csv",
        content=SAMPLE_CSV.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Filament rule",
        account_id=bank.id,
        match_type="contains",
        match_pattern="Filament",
        match_amount_sign="debit",
        action="ignore",
    ))
    await db_session.commit()

    # Sanity: this import has at least 3 unmatched lines, so an N+1 bug
    # would manifest as >=3 calls instead of 1.
    from sqlalchemy import select as _sel
    from app.models.statement_import import StatementLine
    unmatched = (
        await db_session.execute(
            _sel(StatementLine).where(
                StatementLine.import_id == imp.id,
                StatementLine.match_status == "unmatched",
            )
        )
    ).scalars().all()
    assert len(unmatched) >= 3

    calls = {"n": 0}
    real_loader = svc._load_active_rules

    async def counting_loader(db):
        calls["n"] += 1
        return await real_loader(db)

    monkeypatch.setattr(svc, "_load_active_rules", counting_loader)

    summary = await svc.apply_rules_to_import(db_session, import_id=imp.id)

    assert calls["n"] == 1, (
        f"_load_active_rules ran {calls['n']} times for "
        f"{summary['considered']} unmatched lines — expected exactly 1 "
        "(Codex P1 on #281: rules cache per import pass)."
    )
    # And the rule still actually fires under the cached path.
    assert summary["auto_ignored"] == 2


@pytest.mark.asyncio
async def test_evaluate_rules_for_line_standalone_still_self_loads(
    db_session, monkeypatch
):
    """Backward-compat: single-line callers that don't pass `rules=` must
    still work — the function self-fetches in that case."""
    bank = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="csv",
        source_filename="x.csv",
        content=SAMPLE_CSV.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Filament rule",
        account_id=bank.id,
        match_type="contains",
        match_pattern="Filament",
        match_amount_sign="debit",
        action="ignore",
    ))
    await db_session.commit()

    from sqlalchemy import select as _sel
    from app.models.statement_import import StatementLine
    line = (
        await db_session.execute(
            _sel(StatementLine).where(StatementLine.fitid == "FITID001")
        )
    ).scalar_one()

    calls = {"n": 0}
    real_loader = svc._load_active_rules

    async def counting_loader(db):
        calls["n"] += 1
        return await real_loader(db)

    monkeypatch.setattr(svc, "_load_active_rules", counting_loader)

    rule = await svc.evaluate_rules_for_line(db_session, line)

    assert rule is not None
    assert rule.action == "ignore"
    assert calls["n"] == 1  # self-loaded once for this single-line call
