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


SUPPORTED_ACTIONS = {"ignore", "create_journal_entry"}  # #316 P2


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
    matching rule's action.

    Phase 1 supported `ignore`. #316 P2 adds `create_journal_entry`: posts a
    balanced JE against the configured `category_account_id` and the bank
    account, in the direction implied by the statement line's amount sign,
    then sets the line's `match_status` to `matched` and links the new JE.
    Returns a summary dict of counts.
    """
    from app.models.account import Account
    from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
    from app.services.accounting_service import create_journal_entry as _create_je

    lines = (
        await db.execute(
            select(StatementLine).where(
                StatementLine.import_id == import_id,
                StatementLine.match_status == "unmatched",
            )
        )
    ).scalars().all()

    auto_ignored = 0
    auto_je = 0
    skipped_unsupported = 0
    for line in lines:
        rule = await evaluate_rules_for_line(db, line)
        if rule is None:
            continue
        if rule.action == "ignore":
            line.match_status = "ignored"
            auto_ignored += 1
        elif rule.action == "create_journal_entry":
            if rule.category_account_id is None:
                skipped_unsupported += 1
                continue
            cat = (
                await db.execute(select(Account).where(Account.id == rule.category_account_id))
            ).scalar_one_or_none()
            bank = (
                await db.execute(select(Account).where(Account.id == line.account_id))
            ).scalar_one_or_none()
            if cat is None or bank is None:
                skipped_unsupported += 1
                continue
            amt = abs(Decimal(line.amount))
            # Inflow (line.amount > 0): Dr bank, Cr category (income/credit-normal).
            # Outflow (line.amount < 0): Cr bank, Dr category (expense/debit-normal).
            if Decimal(line.amount) >= 0:
                bank_side, cat_side = "debit", "credit"
            else:
                bank_side, cat_side = "credit", "debit"
            je = await _create_je(
                db,
                JournalEntryCreate(
                    entry_date=line.posted_date,
                    memo=f"[rule:{rule.name}] {line.description[:160]}",
                    lines=[
                        JournalLineCreate(account_id=bank.id, entry_type=bank_side, amount=amt),
                        JournalLineCreate(account_id=cat.id, entry_type=cat_side, amount=amt),
                    ],
                ),
            )
            line.match_status = "matched"
            # Link the bank-side JE line so reconciliation pulls it
            from app.models.journal_line import JournalLine

            bank_line = (
                await db.execute(
                    select(JournalLine).where(
                        JournalLine.journal_entry_id == je.id,
                        JournalLine.account_id == bank.id,
                    )
                )
            ).scalar_one()
            line.matched_journal_line_id = bank_line.id
            auto_je += 1
        else:
            skipped_unsupported += 1

    await db.flush()
    return {
        "considered": len(lines),
        "auto_ignored": auto_ignored,
        "auto_journal_entries": auto_je,
        "skipped_unsupported_actions": skipped_unsupported,
    }


async def preview_rules_for_import(
    db: AsyncSession, *, import_id: uuid.UUID
) -> dict:
    """#316 P2: dry-run preview — for every unmatched line return the rule
    that would fire and the action it would take, without actually mutating
    any state.
    """
    from app.models.account import Account

    lines = (
        await db.execute(
            select(StatementLine).where(
                StatementLine.import_id == import_id,
                StatementLine.match_status == "unmatched",
            )
        )
    ).scalars().all()

    out = []
    for line in lines:
        rule = await evaluate_rules_for_line(db, line)
        if rule is None:
            out.append(
                {
                    "statement_line_id": str(line.id),
                    "amount": str(line.amount),
                    "description": line.description,
                    "matched_rule": None,
                }
            )
            continue
        cat_label = None
        if rule.category_account_id is not None:
            cat = (
                await db.execute(select(Account).where(Account.id == rule.category_account_id))
            ).scalar_one_or_none()
            if cat is not None:
                cat_label = f"{cat.code} {cat.name}"
        out.append(
            {
                "statement_line_id": str(line.id),
                "amount": str(line.amount),
                "description": line.description,
                "matched_rule": {
                    "id": str(rule.id),
                    "name": rule.name,
                    "action": rule.action,
                    "category_account": cat_label,
                },
            }
        )
    return {
        "import_id": str(import_id),
        "lines": out,
        "considered": len(lines),
        "would_match": sum(1 for l in out if l["matched_rule"]),
    }


async def create_rule_from_line(
    db: AsyncSession,
    *,
    statement_line_id: uuid.UUID,
    name: str,
    action: str,
    category_account_id: uuid.UUID | None = None,
    match_type: str = "contains",
) -> StatementMatchRule:
    """#316 P2: derive a starter rule from a staged statement line.

    Defaults to a "contains" pattern using a sanitized prefix of the line's
    description. Operator can edit later.
    """
    line = (
        await db.execute(select(StatementLine).where(StatementLine.id == statement_line_id))
    ).scalar_one_or_none()
    if line is None:
        raise StatementMatchRuleError("Statement line not found")
    pattern = (line.description or "").strip()[:120] or name
    sign = "credit" if Decimal(line.amount) >= 0 else "debit"
    validate_rule(
        match_type=match_type,
        match_pattern=pattern,
        match_amount_sign=sign,
        action=action,
    )
    rule = StatementMatchRule(
        name=name,
        account_id=line.account_id,
        match_type=match_type,
        match_pattern=pattern,
        match_amount_sign=sign,
        action=action,
        category_account_id=category_account_id,
    )
    db.add(rule)
    await db.flush()
    return rule


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
