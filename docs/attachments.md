# Attachments (Phase 1)

Operators staple files to records — vendor receipt PDFs on bills, reference photos on jobs, design renders on products. #250.

## Phase 1 scope

- **Polymorphic** via `(scope, record_id)`. Supported scopes:
  `bill`, `invoice`, `quote`, `credit_note`, `debit_note`, `sale`,
  `job`, `product`, `customer`, `vendor`, `material`, `supply`,
  `fixed_asset`, `bank_reconciliation`, `expense_claim`.
- **Storage**: local filesystem at `ATTACHMENT_STORAGE_ROOT` (default `/var/app-attachments`). Files written under `<scope>/<yyyy>/<mm>/<uuid>.<ext>`.
- **Allowed types** (sniffed via magic bytes; extension-only fallback for plaintext): PDF, PNG, JPEG, GIF, WebP, ASCII STL, 3MF (zip-based), text/plain, text/csv. Unknown types are rejected.
- **Size limits**: 20 MB per file, 100 MB cumulative per record.
- **Image thumbnails** generated via Pillow at 256×256 max, stored at `<key>.thumb.webp`.
- **Soft delete** via `deleted_at`; hides from list/download. Underlying file is left on disk for audit (cleanup is a future job).
- **Path-traversal protection**: filenames sanitized; resolved storage paths must stay inside the configured root.
- **Server-proxied download** — the API streams bytes with auth check; no signed URLs.

## API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/attachments/{scope}/{record_id}` | multipart upload (`file`, optional `description`) |
| `GET` | `/api/v1/attachments/{scope}/{record_id}` | List non-deleted attachments |
| `GET` | `/api/v1/attachments/{id}/download` | Server-proxied download |
| `GET` | `/api/v1/attachments/{id}/thumbnail` | 404 for non-images |
| `DELETE` | `/api/v1/attachments/{id}` | Soft delete |

## Deployment

`docker-compose.prod.yml` mounts `attachments_data` at `/var/app-attachments`. **Back this volume up** — attachments are durable file artifacts.

## Phase 2 follow-ups

Each as its own issue when prioritized:

1. **Email-attach hook** for #244's send modal (per-attachment checkbox; selected files attached to the outbound email).
2. **S3-compatible backend** behind the existing path-traversal-safe access pattern. Today the service reads/writes via filesystem — abstraction can grow when needed.
3. **Virus scanning** (ClamAV or similar). Required if customer portal (#257) ever exposes upload to non-operators.
4. **HEIC support** via pillow-heif.
5. **Editable size limits** as settings (currently constants).
6. **Hard-delete cleanup job** running periodically against soft-deleted rows.
7. **Frontend `<AttachmentsPanel scope record_id />`** dropped onto each detail page.
