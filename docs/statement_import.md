# Bank Statement Import (Phase 1)

Operators upload an OFX or CSV statement, the service parses + dedupes
the rows, and a review screen lets the operator match each line to an
existing journal line or ignore it. #240.

## Phase 1 scope

- **Models**: `StatementImport` per upload + `StatementLine` per row.
- **Formats**: OFX (SGML/XML, regex-based parser — no `ofxparse` dep) and CSV with default column names (`Date`, `Amount`, `Description`, `FITID`).
- **Dedup**: by `(account_id, fitid)` when fitid is present; otherwise by exact `(account_id, posted_date, amount, description)` match.
- **Match suggestions**: same account, ±5 days from `posted_date`, exact-amount match, excluding already-reconciled journal lines. Top 5.
- **Match action**: links the statement line to a journal line and promotes the journal line's `cleared_status` to `cleared` (#239's vocabulary).
- **Ignore action**: marks the statement line as ignored (won't show in "needs review").
- **Bank-account guard**: imports refuse on non-bank accounts.

## API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/banking/imports` | multipart upload (`account_id`, `source_format`, `file`). |
| `GET` | `/api/v1/banking/imports?account_id=...` | List recent imports. |
| `GET` | `/api/v1/banking/imports/{import_id}/lines?status_filter=...` | List lines for an import. |
| `GET` | `/api/v1/banking/imports/lines/{line_id}/suggestions` | Top match candidates. |
| `POST` | `/api/v1/banking/imports/lines/{line_id}/match` | Match to a journal line. |
| `POST` | `/api/v1/banking/imports/lines/{line_id}/ignore` | Skip from review. |

## Phase 2 follow-ups

- **Auto-match rules** (#241) — picked up next; depends on this issue's data model. The hooks are in place: rules run during import to auto-handle statement lines that match a configured pattern.
- **CSV column-mapping UI** with saved-per-account mappings (Phase 1 only supports the default headers).
- **QFX / QIF** parsers.
- **Multi-account OFX bundles** — Phase 1 ignores `<BANKACCTFROM>` checks.
- **Create-transaction-from-line** flow — operator can already match against an existing JE; Phase 2 will let them post a new receipt/payment inline.
- **Frontend** review screen for the import.
