"""Bank statement import (#240) Phase 1.

OFX (SGML or XML form) and a basic CSV path. Extracts (date, amount,
description, fitid) per row, dedupes by (account_id, fitid) when fitid
is present, and persists `StatementLine` rows for operator review +
match. Match suggestions are returned at list time.

OFX support is parser-light: the spec is large, but for our use case we
just need to walk STMTTRN records inside an OFX SGML/XML payload. We
implement that with a small regex-based extractor rather than pulling
in the `ofxparse` dep.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.statement_import import StatementImport, StatementLine


class StatementImportError(RuntimeError):
    pass


# ---------- OFX parsing ----------


_TAG_RE = re.compile(r"<(?P<tag>[A-Z][A-Z0-9]+)>(?P<value>[^<]*)", re.IGNORECASE)


def _extract_field(block: str, tag: str) -> str | None:
    """Return the first text-content of a tag inside `block`, or None."""
    for m in _TAG_RE.finditer(block):
        if m.group("tag").upper() == tag.upper():
            return m.group("value").strip()
    return None


def _ofx_parse_date(s: str) -> date:
    """OFX dates: YYYYMMDD or YYYYMMDDHHMMSS[.XXX][Z]; we just need the
    date portion."""
    return datetime.strptime(s[:8], "%Y%m%d").date()


def parse_ofx(content: str) -> list[dict]:
    """Walk every <STMTTRN> block in an OFX payload, returning a list of
    {posted_date, amount, description, fitid} dicts. SGML and XML forms
    both work because we only look at tag patterns inside the block.
    """
    out: list[dict] = []
    # Find every STMTTRN block. OFX SGML doesn't always close tags, but
    # `<STMTTRN>...</STMTTRN>` is consistently delimited. We allow either
    # the SGML close tag or the next <STMTTRN> as the boundary.
    pattern = re.compile(
        r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|<\/BANKTRANLIST>|<BANKTRANLIST>|$)",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(content):
        block = m.group(1)
        dtposted = _extract_field(block, "DTPOSTED")
        trnamt = _extract_field(block, "TRNAMT")
        if dtposted is None or trnamt is None:
            continue
        try:
            posted = _ofx_parse_date(dtposted)
            amount = Decimal(trnamt.strip())
        except (ValueError, ArithmeticError):
            continue
        fitid = _extract_field(block, "FITID")
        memo = _extract_field(block, "MEMO") or ""
        name = _extract_field(block, "NAME") or ""
        description = (memo + " " + name).strip() or "(unknown)"
        out.append(
            {
                "posted_date": posted,
                "amount": amount,
                "description": description[:500],
                "fitid": fitid.strip() if fitid else None,
            }
        )
    return out


def parse_csv(content: str, *, mapping: dict[str, str] | None = None) -> list[dict]:
    """Parse a CSV with header row. `mapping` overrides which CSV column
    name to use for each field; defaults to common names.
    """
    mapping = mapping or {
        "date": "Date",
        "amount": "Amount",
        "description": "Description",
        "fitid": "FITID",
    }
    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        date_str = (row.get(mapping["date"]) or "").strip()
        amt_str = (row.get(mapping["amount"]) or "").strip()
        desc = (row.get(mapping["description"]) or "").strip()
        if not date_str or not amt_str:
            continue
        # Try a few common date formats
        posted = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
            try:
                posted = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        if posted is None:
            continue
        try:
            amount = Decimal(amt_str.replace(",", "").replace("$", ""))
        except ArithmeticError:
            continue
        fitid = (row.get(mapping["fitid"]) or "").strip() or None
        out.append(
            {
                "posted_date": posted,
                "amount": amount,
                "description": desc[:500],
                "fitid": fitid,
            }
        )
    return out


# ---------- import ----------


async def import_statement(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    source_format: str,
    source_filename: str,
    content: bytes,
    imported_by_user_id: uuid.UUID | None = None,
) -> StatementImport:
    if source_format not in ("ofx", "csv"):
        raise StatementImportError(f"Unsupported format: {source_format}")
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if account is None:
        raise StatementImportError("Account not found")
    if not account.is_bank_account:
        raise StatementImportError(f"Account {account.code} is not a bank account")

    text = content.decode("utf-8", errors="replace")
    rows = parse_ofx(text) if source_format == "ofx" else parse_csv(text)

    imp = StatementImport(
        account_id=account.id,
        source_format=source_format,
        source_filename=source_filename,
        imported_by_user_id=imported_by_user_id,
    )
    db.add(imp)
    await db.flush()

    line_count = 0
    duplicate_count = 0
    for row in rows:
        fitid = row["fitid"]
        # Dedup against (account_id, fitid) when fitid is present
        if fitid:
            dup = (
                await db.execute(
                    select(StatementLine.id).where(
                        StatementLine.account_id == account.id,
                        StatementLine.fitid == fitid,
                    )
                )
            ).first()
            if dup:
                duplicate_count += 1
                continue
        # Without a fitid, fall back to (account_id, date, amount, description)
        # exact match.
        else:
            dup = (
                await db.execute(
                    select(StatementLine.id).where(
                        and_(
                            StatementLine.account_id == account.id,
                            StatementLine.posted_date == row["posted_date"],
                            StatementLine.amount == row["amount"],
                            StatementLine.description == row["description"],
                        )
                    )
                )
            ).first()
            if dup:
                duplicate_count += 1
                continue
        db.add(
            StatementLine(
                import_id=imp.id,
                account_id=account.id,
                posted_date=row["posted_date"],
                amount=row["amount"],
                description=row["description"],
                fitid=fitid,
                match_status="unmatched",
            )
        )
        line_count += 1

    imp.line_count = line_count
    imp.duplicate_count = duplicate_count
    await db.flush()
    return imp


# ---------- match ----------


async def suggest_matches(
    db: AsyncSession,
    *,
    statement_line_id: uuid.UUID,
    limit: int = 5,
) -> list[JournalLine]:
    """Return up to `limit` candidate journal lines for the statement line,
    ranked by closeness on (date, amount). v1 keeps it simple: same account,
    date within ±5 days, exact amount match.
    """
    sl = (await db.execute(select(StatementLine).where(StatementLine.id == statement_line_id))).scalar_one_or_none()
    if sl is None:
        raise StatementImportError("Statement line not found")

    from datetime import timedelta

    lo = sl.posted_date - timedelta(days=5)
    hi = sl.posted_date + timedelta(days=5)

    # Match on signed amount: a debit on a debit-normal asset means cash IN
    # (positive on the bank statement). For now we ignore sign nuance and
    # let exact-amount matching find candidates regardless of side.
    rows = (
        await db.execute(
            select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(
                JournalLine.account_id == sl.account_id,
                JournalLine.cleared_status != "reconciled",
                JournalEntry.entry_date >= lo,
                JournalEntry.entry_date <= hi,
                JournalLine.amount == abs(sl.amount),
            )
            .order_by(JournalEntry.entry_date)
            .limit(limit)
        )
    ).all()
    return [line for line, _entry in rows]


async def match_line(
    db: AsyncSession,
    *,
    statement_line_id: uuid.UUID,
    journal_line_id: uuid.UUID,
) -> StatementLine:
    sl = (await db.execute(select(StatementLine).where(StatementLine.id == statement_line_id))).scalar_one_or_none()
    if sl is None:
        raise StatementImportError("Statement line not found")
    if sl.match_status == "matched":
        raise StatementImportError("Statement line is already matched")

    jl = (await db.execute(select(JournalLine).where(JournalLine.id == journal_line_id))).scalar_one_or_none()
    if jl is None:
        raise StatementImportError("Journal line not found")
    if jl.account_id != sl.account_id:
        raise StatementImportError("Journal line account does not match the statement account")

    sl.matched_journal_line_id = jl.id
    sl.match_status = "matched"
    # Promote the journal line to cleared (#239's vocabulary) so the
    # reconciliation worksheet sees it.
    if jl.cleared_status == "uncleared":
        jl.cleared_status = "cleared"
    await db.flush()
    return sl


async def ignore_line(db: AsyncSession, statement_line_id: uuid.UUID) -> StatementLine:
    sl = (await db.execute(select(StatementLine).where(StatementLine.id == statement_line_id))).scalar_one_or_none()
    if sl is None:
        raise StatementImportError("Statement line not found")
    sl.match_status = "ignored"
    await db.flush()
    return sl
