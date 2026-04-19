# n8n Deploy Workflow for web01

This is the operator-facing runbook for the `web01-deploy` n8n workflow. It covers setup, triggering, reading results, adjusting the workflow, and recovering from failures.

The workflow definition lives at [`ops/n8n/web01-deploy.json`](../ops/n8n/web01-deploy.json) and is the canonical path for deploying new versions of this application to `web01`. The manual SSH sequence documented in [`agents.md`](../agents.md) remains available as a fallback if n8n is unavailable.

## Purpose

Codify the canonical web01 deploy sequence so that every release is:

- **Re-usable** — same exact steps every time, triggered from a webhook or a button
- **Monitored** — every run shows per-step output, duration, and status in n8n's execution view
- **Adjustable** — each step is a discrete node; add, reorder, or remove without rewriting shell scripts
- **Safe** — failures halt the workflow, fire a notification, and never leave the system in an unknown state
- **Auditable** — execution history records what was triggered, by whom, and the commit that was deployed

## What the workflow does

In order:

1. Accepts a trigger payload: `{ branch, run_migrations?, force_rebuild?, triggered_by? }`.
2. Validates input (branch allowlist: `main`, `staging`).
3. SSH to `web01.bengtson.local` and verifies reachability.
4. Verifies the server-side git working tree is clean.
5. Captures the current commit SHA (`before_sha`).
6. `git fetch` and `git pull` the target branch.
7. Captures the new commit SHA (`after_sha`).
8. Diffs `backend/alembic/versions/` between the two SHAs to decide whether migrations are needed (or honours an explicit `run_migrations: true|false`).
9. If migrations needed: runs `scripts/web01-compose.sh exec -T backend alembic upgrade head`.
10. Runs `scripts/web01-compose.sh up -d --build` to rebuild and restart containers.
11. Waits 15 seconds for containers to settle.
12. Verifies all three containers (`db`, `backend`, `frontend`) are healthy via `scripts/web01-compose.sh ps`.
13. Verifies `GET /health` returns 200.
14. Verifies `GET /` returns 200.
15. Builds a success summary and fires the success notification webhook (if configured).
16. Responds to the original trigger with a JSON summary.

On any failure along the way, the workflow routes to an error-handling branch that:

- Captures the failed-step name and error message.
- Tails the last 50 lines of `backend` and `frontend` container logs (best effort).
- Fires a failure notification webhook (if configured).
- Responds to the original trigger with a `500` status and a detailed failure body.

## First-time setup

### 1. Install n8n

Recommended: run n8n on a machine that is **not** web01 (a local workstation or a small VM), so n8n is independent of the deploy target.

Minimum: Docker on the host.

```bash
docker run -d --restart unless-stopped \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -e N8N_SECURE_COOKIE=false \
  -e GENERIC_TIMEZONE=America/Chicago \
  n8nio/n8n:latest
```

Visit `http://<n8n-host>:5678` and create an owner account.

### 2. Create credentials

The workflow requires two credentials in n8n. Both are referenced by **name** inside the workflow JSON, so the names matter.

#### a) `web01.bengtson.local` (SSH Private Key)

> **This repository already has this credential configured on the target n8n instance.** The steps below are for reference / disaster-recovery if the credential is ever lost.

1. **Credentials** → **Add credential** → select **SSH**.
2. Authentication: **Private Key**.
3. Host: `web01.bengtson.local`.
4. Username: `root`.
5. Private Key: paste the content of a key whose matching public key is in `root@web01.bengtson.local:~/.ssh/authorized_keys`.
6. Name the credential exactly `web01.bengtson.local`.
7. Click **Test** to verify, then **Save**.

Hardening recommendations on the web01 side:
- Use a dedicated keypair (not your personal key).
- In `~/.ssh/authorized_keys`, constrain the key with `from="<n8n host IP>"` so it can only be used from the expected source.
- Rotate annually.

#### b) `web01-deploy-webhook-token` (HTTP Header Auth)

1. **Credentials** → **Add credential** → select **Header Auth**.
2. Name: `Authorization`.
3. Value: `Bearer <generate-a-long-random-token>`.
4. Name the credential exactly `web01-deploy-webhook-token`.
5. Save.

Keep the token in your password manager. You will pass it in the `Authorization` header on every webhook call.

### 3. Import the workflow

1. **Workflows** → **Add workflow** → **Import from File**.
2. Select `ops/n8n/web01-deploy.json` from this repository.
3. Verify credentials are resolved (no red badges on any node). If a node shows a broken credential, click the node and bind the credential by name.
4. Optionally set the **n8n variable** `DEPLOY_NOTIFICATION_URL` under **Variables** to a Slack/Discord/Mattermost inbound webhook URL. If unset, the notification nodes are no-ops.
5. Set **Workflow settings** → **Execution** → **Execution concurrency: 1** (so two deploys can never overlap).
6. Set **Workflow settings** → **Execution Timeout: 600s** (matches the default in the JSON).
7. **Activate** the workflow (toggle in the top-right) so the webhook endpoint is live.

### 4. Verify the webhook URL

After activation, the Webhook Trigger node shows a production URL like:

```
https://<your-n8n-host>/webhook/web01-deploy
```

Save that URL; it's how all external callers (Claude, GitHub Actions, scripts) will trigger a deploy.

## Triggering a deploy

### From `curl`

```bash
curl -X POST "https://<your-n8n-host>/webhook/web01-deploy" \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"branch": "main", "triggered_by": "cli"}'
```

### From the n8n UI (manual)

1. Open the `web01-deploy` workflow.
2. Click **Execute Workflow**.
3. When prompted for trigger data, the manual trigger runs with defaults (`branch=main`, `run_migrations=auto`, `force_rebuild=true`, `triggered_by=manual`). To override, edit the **Validate Input** code node temporarily, or use the webhook path instead.

### From Claude / an assistant

Ask Claude to run:

```bash
curl -X POST "$N8N_WEBHOOK" \
  -H "Authorization: Bearer $N8N_DEPLOY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"branch": "main", "triggered_by": "claude"}'
```

Store `N8N_WEBHOOK` and `N8N_DEPLOY_TOKEN` in whatever env/keychain Claude has access to.

### Payload parameters

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `branch` | string | `"main"` | Branch on the server-side checkout to deploy. Must be in the allowlist (`main`, `staging`). Extend the allowlist by editing the `Validate Input` node. |
| `run_migrations` | `"auto" \| true \| false` | `"auto"` | `auto` = run migrations when the `backend/alembic/versions/` diff between SHAs is non-empty. `true` = force migrations even if no new files. `false` = skip migrations (rarely useful). |
| `force_rebuild` | boolean | `true` | Currently unused by the workflow (always runs `up -d --build`). Reserved for future use. |
| `triggered_by` | string | `"manual"` | Free-text identifier for the caller (e.g. `claude`, `cli`, `github-actions`). Shown in the notification and response. |
| `commit` | string | `null` | Reserved — explicit commit to check out. Not implemented in v1 (the server pulls HEAD of `branch`). |

## Reading results

### Success response (HTTP 200)

```json
{
  "ok": true,
  "branch": "main",
  "before_sha": "30e19bf74f84fd21a86f225512234b16c6a60d25",
  "after_sha": "c3decb32cbbf765723a1bd2192ad6a64c5e75d5a",
  "migrations_run": true,
  "migration_files": ["backend/alembic/versions/20260412_01_add_cameras.py"],
  "duration_seconds": 142,
  "containers": [
    { "name": "3d-print-sales-db", "state": "running", "health": "healthy", "found": true },
    { "name": "3d-print-sales-backend", "state": "running", "health": "healthy", "found": true },
    { "name": "3d-print-sales-frontend", "state": "running", "health": "healthy", "found": true }
  ],
  "health_endpoint": "{\"status\":\"healthy\"}",
  "frontend_endpoint": "HTTP/1.1 200 OK",
  "triggered_by": "claude",
  "started_at": "2026-04-19T14:55:00Z",
  "finished_at": "2026-04-19T14:57:22Z"
}
```

### Failure response (HTTP 500)

```json
{
  "ok": false,
  "branch": "main",
  "failed_at_step": "SSH: Run Migrations",
  "error": "Command failed: alembic.util.exc.CommandError: Can't locate revision identified by '20260412_02'",
  "log_tail": "... last 50 lines of backend/frontend logs ...",
  "duration_seconds": 58,
  "triggered_by": "claude",
  "started_at": "2026-04-19T14:55:00Z",
  "finished_at": "2026-04-19T14:55:58Z"
}
```

### In the n8n UI

1. **Executions** → filter by workflow `web01-deploy`.
2. Click a row to view per-node status, input/output, duration, error trace.
3. Failed executions are highlighted in red.

### Notifications

If `DEPLOY_NOTIFICATION_URL` is configured, both success and failure post to that URL with a payload like:

```json
{ "type": "success", "summary": { /* same shape as response */ } }
```

or

```json
{ "type": "failure", "summary": { /* failure response */ } }
```

This can be wired to Slack/Discord/Mattermost inbound webhooks, a custom relay, or an email-forwarding service.

## Adjusting the workflow

Every step is a discrete node. Common changes:

- **Add a post-deploy smoke test** — add an SSH node between `SSH: GET / (frontend)` and `Build Success Summary` that hits another endpoint (e.g. `curl /api/v1/auth/me` with a known token).
- **Change the wait time** — edit the `Wait for containers` node's duration.
- **Extend the branch allowlist** — edit the `ALLOWED_BRANCHES` array in the `Validate Input` node.
- **Change the notification destination** — set the `DEPLOY_NOTIFICATION_URL` n8n variable.
- **Run a pre-deploy DB backup** — insert a new SSH node before `SSH: Compose up --build` that runs `pg_dump` into a dated file on the host.
- **Enable error workflow routing** — under **Workflow settings**, point the `errorWorkflow` setting to a separate n8n workflow that handles any uncaught errors (e.g. notify on SSH credential expiry).

After editing, **download** the workflow JSON from n8n and overwrite `ops/n8n/web01-deploy.json` in this repo, then commit.

## Rollback procedure

This workflow does **not** perform automatic rollback on failure. If a deploy leaves the app degraded, the operator has these options, in order of preference:

### Option 1 — rerun a known-good commit

```bash
# SSH to web01
ssh root@web01.bengtson.local
cd /srv/3d-print-sales/repo
git checkout <known-good-sha>
scripts/web01-compose.sh up -d --build
```

Then trigger the workflow with the same SHA on `main` via the UI.

### Option 2 — `alembic downgrade -1` on migration failure

```bash
ssh root@web01.bengtson.local
cd /srv/3d-print-sales/repo
scripts/web01-compose.sh exec -T backend alembic downgrade -1
```

### Option 3 — systemd restart

If containers are running but unhealthy due to a startup bug:

```bash
ssh root@web01.bengtson.local
systemctl restart 3d-print-sales.service
```

A future iteration of the workflow can include automatic rollback logic — tracked as a follow-up beyond issue #164.

## Security model

- **SSH private key** stored only as an n8n credential (encrypted at rest in n8n's DB). Referenced in the workflow JSON by **name only**, never inlined.
- **Webhook bearer token** stored only as an n8n credential. Every external trigger must present it.
- **Branch allowlist** enforced at the `Validate Input` node.
- **Command templates** — every SSH command is a hardcoded template. The only user-controlled value is `branch`, which is allowlist-checked before being interpolated.
- **Concurrency limit** — set per workflow to `1` to prevent overlapping deploys.
- **No secrets in logs** — the workflow does not echo environment variables or credentials.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Node error: `Command failed: Permission denied (publickey)` | SSH credential wrong or public key not in `authorized_keys` | Verify n8n credential; `ssh-copy-id` the public key |
| Node error: `Branch "xyz" is not in the allowlist` | Caller passed an unsupported branch | Either use `main`/`staging`, or edit the allowlist in `Validate Input` |
| Node error: `web01 working tree is dirty` | Someone hand-edited files in `/srv/3d-print-sales/repo` | `ssh` to web01, resolve with `git stash` or `git reset --hard HEAD` |
| Workflow succeeds but `/health` returns 502 | Backend container is up but failing to start | Check execution — `SSH: GET /health` output will be empty. `compose logs backend` on host |
| Notification never fires | `DEPLOY_NOTIFICATION_URL` variable not set | Set it under **Variables** or remove the `Notify Success/Failure` nodes |
| Webhook returns 401 | Bearer token missing or wrong | Verify `Authorization: Bearer <token>` matches the `web01-deploy-webhook-token` credential |
| Two deploys ran at the same time | Concurrency limit not configured | **Workflow settings** → **Execution concurrency: 1** |

## Related references

- `agents.md` — authoritative operating guide, including the manual SSH deploy fallback.
- `ops/n8n/README.md` — import/export and directory-level documentation.
- `ops/n8n/web01-deploy.json` — the canonical workflow definition.
- Issue #164 — the original user story and acceptance criteria that drove this workflow.
