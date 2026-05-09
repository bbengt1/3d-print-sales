# Outbound Email — Phase 1

Operators send invoices and quotes to customers via SMTP. Each send persists an `EmailDelivery` audit row (sent / failed) so the history is visible per record.

## Phase 1 scope (this PR)

- **Transport: SMTP only.** Generic SMTP host + port + STARTTLS + login.
- **Body: HTML + plain-text alternative.** Hard-coded templates for `invoice` and `quote` (see `app/services/email_service.py`).
- **Audit: every send persists a row** in `email_deliveries` with status `sent` or `failed` and the SMTP `Message-ID`.
- **No attachments.** PDF generation deferred to Phase 2 (needs WeasyPrint + Cairo/Pango in the Docker image).
- **No Resend transport.** Deferred to Phase 2.
- **No delivery-status webhooks.** SMTP doesn't provide them; Resend does, but Resend is Phase 2.
- **No opens tracking.** Tied to a transactional provider (Phase 2).
- **No editable templates.** Phase 1 uses code-defined templates; Phase 2 promotes to operator-editable settings (which requires a Setting.value column type bump from String(255) → Text — also deferred).

## Settings (admin)

| Key | Default | Notes |
|---|---|---|
| `email_transport` | `smtp` | Future: `resend` |
| `email_smtp_host` | (empty) | e.g. `smtp.gmail.com`, `smtp.sendgrid.net` |
| `email_smtp_port` | `587` | 587 STARTTLS, 465 SMTPS, 25 plaintext |
| `email_smtp_username` | (empty) | |
| `email_smtp_password` | (empty) | **Plaintext in v1.** Encryption-at-rest deferred. Use a sender-only API token (e.g. SendGrid restricted key, Postmark API token) rather than your real account password. |
| `email_smtp_use_tls` | `true` | Whether to STARTTLS after EHLO |
| `email_from_address` | (empty) | |
| `email_from_name` | (empty) | Falls back to from_address if blank |

If `email_smtp_host` or `email_from_address` is unset, the send endpoints return 400 with a clear "transport not configured" message.

## API

- `POST /api/v1/invoices/{invoice_id}/email` — body: `{ to_email?, cc?, bcc?, subject_override? }`. Resolves `to_email` from the invoice's customer email if not supplied. Returns the `EmailDelivery` row.
- `POST /api/v1/quotes/{quote_id}/email` — same shape against quotes.
- `GET /api/v1/invoices/{id}/email-deliveries` and `GET /api/v1/quotes/{id}/email-deliveries` — history list, newest first.

The send is **synchronous** — the API call blocks on the SMTP round-trip (typically 0.5–2s; up to ~30s on flaky transports). On send failure the `EmailDelivery` row is still persisted with `status='failed'` so the audit trail is complete; the API returns 502 to the caller.

## Operator runbook

1. Pick an SMTP provider (Gmail SMTP for personal, SendGrid / Postmark / Mailgun for business). Generate a sender-only API token.
2. In settings, set `email_smtp_host`, `email_smtp_port`, `email_smtp_username`, `email_smtp_password`, `email_from_address`, `email_from_name`.
3. Test by issuing `POST /api/v1/invoices/{id}/email` against a real invoice (or via the upcoming frontend send modal).
4. If the send fails, check the `email_deliveries` row's `error` column for the SMTP exception.

## Phase 2 follow-ups (track separately)

These are intentionally not in this PR; each can be its own issue when prioritized.

1. **WeasyPrint PDF rendering** for invoice/quote attachments. Adds Cairo/Pango/gdk-pixbuf system deps to the Docker image. Render an invoice/quote to PDF and attach to the outbound email.
2. **Resend transport.** Pluggable transport interface + `ResendEmailTransport`. Adds `httpx` POST to `https://api.resend.com/emails`.
3. **Resend webhook.** Signature verification via `svix`, status updates on `EmailDelivery` (`delivered`, `bounced`, `complained`, opens count).
4. **Opens tracking pixel** (Resend-provided).
5. **Editable templates** in settings. Requires extending `Setting.value` from `String(255)` → `Text`.
6. **At-rest encryption** for `email_smtp_password` (Fernet via app secret key).
7. **Frontend send modal** with PDF preview and editable subject/body. Currently no invoice/quote create UI exists in the React surface (API-only); the modal would land alongside whichever issue introduces those forms.

## Phase 1 limitations to call out to operators

- **No PDF attachment.** The body has a summary; for the full invoice/quote line breakdown the customer should still log into the admin (or wait for Phase 2).
- **Plaintext password storage.** Use a restricted API token, not your account password.
- **No retry.** A 502 on send means try again from the UI; that creates a new `EmailDelivery` row each time.
