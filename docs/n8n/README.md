# n8n workflow templates

JSON exports of recommended n8n workflows for cron-style entry points exposed by the backend. Import via n8n's **Workflows → Import from file** menu.

## Required environment variables (set as n8n credentials/env)

- `APP_BASE_URL` — e.g. `https://web01.bengtson.local`
- `APP_API_TOKEN` — a long-lived bearer token for an admin user (mint via the user management API)

## Templates

| File | Backend endpoint it calls | Cadence | Notes |
|---|---|---|---|
| `recurring-journal-entries-cron.json` | `POST /api/v1/accounting/recurring-journal-entries/run-due` | Daily 06:00 | Generates due recurring journal entries (#260 / #330 P2). Logs to optional Slack node. |
| `recurring-invoices-cron.json` | `POST /api/v1/recurring-invoices/run-due` | Daily 06:00 | Generates due recurring invoices and (when `auto_email` is on) sends them via the SMTP path (#247 + #244 P2). |

The Slack node is optional — delete it from the workflow if you don't want notifications. The HTTP node will still process all due entries.
