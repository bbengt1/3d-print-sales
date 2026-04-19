# ops/n8n

Version-controlled n8n workflows used to operate this application.

The human-readable runbook lives at [`docs/deployment_n8n_workflow.md`](../../docs/deployment_n8n_workflow.md). This directory is the source of the workflow JSON itself.

## Contents

| File | Purpose |
|------|---------|
| `web01-deploy.json` | Primary deploy workflow for `web01`. Pulls latest, rebuilds containers, runs migrations, verifies health. |

## Importing a workflow into n8n

1. Open the n8n UI.
2. Click **Workflows** → **Add workflow** → **Import from File**.
3. Select the JSON file from this directory (e.g. `web01-deploy.json`).
4. After import, click into the workflow and verify each SSH node's credential binding shows `web01.bengtson.local` (the credential must already exist in n8n — see the runbook).
5. If the webhook node shows a broken credential, create (or bind an existing) Header Auth credential named `web01-deploy-webhook-token` — see runbook.
6. Save the workflow.

## Exporting edits back to this repo

After editing a workflow in n8n:

1. Open the workflow in n8n.
2. Menu (three dots) → **Download**. This produces a JSON file.
3. Overwrite the corresponding file in this directory.
4. Open the diff locally and confirm no credential IDs or private-key material leaked into the export. n8n exports credentials by `name` only, but always verify.
5. Commit the updated JSON with a short message like `ops(n8n): update web01-deploy to add <change>`.

## Credentials assumed to exist in n8n

The exported workflow references credentials by **name** (no IDs, no secrets). The target n8n instance must have:

| Credential name | Type | Used by |
|-----------------|------|---------|
| `web01.bengtson.local` | SSH (Private Key) | every SSH node in the workflow |
| `web01-deploy-webhook-token` | HTTP Header Auth | the Webhook trigger node |

If either is missing, the workflow will load but will error at the first node that needs the credential. The runbook documents how to create them from scratch.

## Concurrency and safety

Set **workflow settings → Execution → Execution concurrency** to `1` after import. The workflow JSON cannot encode instance-level concurrency limits; this must be configured once per-instance.

## Why the workflow JSON is committed

- Disaster recovery — the workflow is reproducible from source if the n8n instance is lost.
- Code review — changes to the deploy flow are diffable and reviewable in PRs.
- Documentation — the nodes, commands, and logic are plain text rather than UI-only state.
