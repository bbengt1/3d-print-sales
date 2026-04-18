# Fresh Start Guide

This is the canonical fresh-start setup path for the repository.

Use this guide when you are standing the app up from a clean machine or validating that the repository is deployable without maintainer-only knowledge.

## Prerequisites

Local development path:

- Docker Desktop or Docker Engine with the Compose plugin
- Git

Native validation path:

- Python `3.13`
- Node `22`
- PostgreSQL `16`

Python `3.14` is not currently a supported backend interpreter for this repository. The pinned `pydantic-core` build chain currently tops out at Python `3.13`, so use the repo's `.python-version` or an explicit `python3.13` install for native backend work.

## Fastest Local Bring-Up

Generate a usable development env file from the tracked template:

```bash
./scripts/bootstrap-env.sh local
```

That creates `.env` with randomized values for:

- `DB_PASSWORD`
- `SECRET_KEY`
- `ADMIN_PASSWORD`

Then start the stack:

```bash
docker compose up -d --build
```

Expected local URLs:

- frontend: `http://localhost:5173`
- backend health: `http://localhost:8000/health`
- swagger: `http://localhost:8000/api/v1/docs`

Notes:

- the backend seeds an admin user from `ADMIN_EMAIL` and `ADMIN_PASSWORD` on first startup
- development startup uses `AUTO_CREATE_SCHEMA=true`, so the app creates tables automatically and then runs seed logic
- the development database healthcheck now respects custom `DB_USER` and `DB_NAME` values from `.env`

## Manual Local Env Setup

If you prefer to edit the env file yourself:

```bash
cp .env.example .env
```

Before startup, replace the tracked placeholder values for:

- `DATABASE_URL` or the `DB_*` fields
- `SECRET_KEY`
- `ADMIN_PASSWORD`

The backend refuses to start while tracked placeholder secrets remain in place.

## Native Backend And Frontend Validation

Backend:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m pytest backend/tests -q
```

Frontend:

```bash
cd frontend
npm ci
npm test
npm run build
```

## Production-Like Compose Flow

The maintained production target in this repository is `web01`, which runs from `/srv/3d-print-sales/repo`.

Generate a server env file from the production example:

```bash
./scripts/bootstrap-env.sh web01 --output /srv/3d-print-sales/env/web01.env
```

Then run compose with that env file:

```bash
ENV_FILE=/srv/3d-print-sales/env/web01.env docker compose -f docker-compose.prod.yml up -d --build
```

The canonical wrapper used on `web01` is:

```bash
cd /srv/3d-print-sales/repo
scripts/web01-compose.sh up -d --build
```

Production notes:

- production compose requires `ENV_FILE`
- production startup is migration-driven; it does not rely on `create_all()`
- production frontend serves nginx on `FRONTEND_HTTP_PORT` and proxies `/api/v1` to the backend container

## Post-Start Validation

Local validation:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/health
```

`web01` validation:

```bash
cd /srv/3d-print-sales/repo
scripts/web01-compose.sh ps
curl -fsS http://127.0.0.1/health
curl -I http://127.0.0.1/
```

## Where To Go Next

- [Documentation Hub](index.md)
- [Technical Reference Map](reference/index.md)
- [web01 Runbook](deployment_web01_runbook.md)
