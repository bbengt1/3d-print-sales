"""Auto-match rules for imported statement lines (#241).

Phase 1: only the `ignore` action is implemented — match by description
pattern (contains or regex) plus optional amount-sign filter, and the
matching statement line is set to `ignored` immediately during import
review. Phase 2 will add `create_receipt`/`create_payment` actions that
auto-post a real JE.

Rules are evaluated in priority order (lower number first). First match
wins.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statement_import import StatementLine
from app.models.statement_match_rule import StatementMatchRule


class StatementMatchRuleError(RuntimeError):
    pass


SUPPORTED_ACTIONS = {"ignore"}  # Phase 1


def _matches_pattern(rule: StatementMatchRule, description: str) -> bool:
    if rule.match_type == "contains":
        return rule.match_pattern.lower() in description.lower()
    if rule.match_type == "regex":
        try:
            return re.search(rule.match_pattern, description, re.IGNORECASE) is not None
        except re.error:
            return False
    return False


def _matches_sign(rule: StatementMatchRule, amount: Decimal) -> bool:
    if rule.match_amount_sign == "any":
        return True
    if rule.match_amount_sign == "debit":
        return amount < 0  # outflow
    if rule.match_amount_sign == "credit":
        return amount > 0  # inflow
    return False


async def evaluate_rules_for_line(
    db: AsyncSession, line: StatementLine
) -> StatementMatchRule | None:
    """Return the highest-priority active rule that matches the line, or None."""
    rules = (
        await db.execute(
            select(StatementMatchRule).where(
                StatementMatchRule.is_active == True,  # noqa: E712
            ).order_by(StatementMatchRule.priority.asc(), StatementMatchRule.created_at.asc())
        )
    ).scalars().all()
    for rule in rules:
        if rule.account_id is not None and rule.account_id != line.account_id:
            continue
        if not _matches_pattern(rule, line.description):
            continue
        if not _matches_sign(rule, Decimal(line.amount)):
            continue
        return rule
    return None


async def apply_rules_to_import(
    db: AsyncSession, *, import_id: uuid.UUID
) -> dict:
    """Walk every unmatched line for the given import and apply the first
    matching rule's action. Phase 1: only `ignore` is acted upon.
    Returns a summary dict of counts.
    """
    lines = (
        await db.execute(
            select(StatementLine).where(
                StatementLine.import_id == import_id,
                StatementLine.match_status == "unmatched",
            )
        )
    ).scalars().all()

    auto_ignored = 0
    skipped_unsupported = 0
    for line in lines:
        rule = await evaluate_rules_for_line(db, line)
        if rule is None:
            continue
        if rule.action == "ignore":
            line.match_status = "ignored"
            auto_ignored += 1
        else:
            # Phase 2 actions surfaced but not yet executed
            skipped_unsupported += 1

    await db.flush()
    return {
        "considered": len(lines),
        "auto_ignored": auto_ignored,
        "skipped_unsupported_actions": skipped_unsupported,
    }


def validate_rule(
    *,
    match_type: str,
    match_pattern: str,
    match_amount_sign: str,
    action: str,
) -> None:
    if match_type not in ("contains", "regex"):
        raise StatementMatchRuleError(f"Unknown match_type: {match_type}")
    if not match_pattern:
        raise StatementMatchRuleError("match_pattern is required")
    if match_type == "regex":
        try:
            re.compile(match_pattern)
        except re.error as e:
            raise StatementMatchRuleError(f"Invalid regex: {e}") from e
    if match_amount_sign not in ("debit", "credit", "any"):
        raise StatementMatchRuleError(f"Unknown match_amount_sign: {match_amount_sign}")
    if action not in SUPPORTED_ACTIONS:
        raise StatementMatchRuleError(
            f"Action {action!r} is declared but not implemented in Phase 1; "
            f"supported actions: {sorted(SUPPORTED_ACTIONS)}"
        )
