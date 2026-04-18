# Packageability Audit

This document captures the concrete fresh-start packageability gaps that were addressed as part of issue `#136`.

## Resolved Gaps

### Missing documentation entry points

The repo instructions and `AGENTS.md` referenced these maintained entry points:

- `docs/index.md`
- `docs/reference/index.md`
- `docs/README.md`

Those files did not exist, which made the documentation structure harder to navigate for a new adopter.

Resolved by adding the missing docs hub and reference map.

### Manual secret generation blocked first startup

The tracked env examples intentionally use placeholder secrets, and the backend refuses to start while placeholders remain in place. That is correct from a security perspective, but it meant the quick-start flow was not actually runnable from a clean checkout without manual secret creation.

Resolved by adding [`../scripts/bootstrap-env.sh`](../scripts/bootstrap-env.sh) so a new operator can generate a valid `.env` or server env file from the tracked templates.

### Development compose healthcheck assumed default database identifiers

`docker-compose.yml` used `pg_isready -U printuser -d printsales` even when `.env` changed `DB_USER` or `DB_NAME`. That meant fresh-start validation only worked reliably with the baked-in defaults.

Resolved by making the healthcheck honor `DB_USER` and `DB_NAME`.

### Backend container Python version did not match the documented baseline

The repository documentation and `.python-version` declare Python `3.13`, but the backend container used `python:3.12-slim`.

Resolved by aligning the backend Docker image with Python `3.13`.

## Current Fresh-Start Path

Local:

1. `./scripts/bootstrap-env.sh local`
2. `docker compose up -d --build`
3. verify `http://localhost:8000/health`

Server / `web01`:

1. `./scripts/bootstrap-env.sh web01 --output /srv/3d-print-sales/env/web01.env`
2. `scripts/web01-compose.sh up -d --build`
3. verify compose health and reachability

## Remaining Operator Expectations

These are still expected and are now documented rather than implicit:

- Docker-based production relies on a server-side env file and migration-driven schema management
- seeded admin credentials come from env configuration and should be rotated as part of first access
- `web01` remains the canonical live deployment target described by the repository
- native backend development currently requires Python `3.13`; Python `3.14` is not yet compatible with the pinned backend dependency set
