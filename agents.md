# Agents Guide

## Overview

- This repository is a full-stack 3D print business app.
- Backend: FastAPI, SQLAlchemy async, Alembic, PostgreSQL, pytest.
- Frontend: React, TypeScript, Vite, TanStack Query, Zustand.
- Main business domains: jobs, inventory, sales, printers, accounting, invoices, reports.

## Repository Map

- `backend/app/main.py`: FastAPI app setup, middleware, lifespan hooks, router registration.
- `backend/app/api/v1/endpoints/`: API surface. Most business changes start here plus a service.
- `backend/app/services/`: pricing, inventory, accounting, printer monitoring, reporting logic.
- `backend/app/models/`: SQLAlchemy models.
- `backend/app/schemas/`: request/response models.
- `backend/alembic/versions/`: schema migrations.
- `backend/tests/`: backend coverage. `conftest.py` sets `TESTING=true` and swaps DB dependencies.
- `frontend/src/pages/`: route-level UI.
- `frontend/src/components/`: layout, auth, and shared UI.
- `frontend/src/api/client.ts`: axios instance and auth redirect behavior.
- `frontend/src/store/auth.ts`: persisted auth state.

## Working Rules

- Keep API, schema, model, and frontend type changes in sync. This repo has many parallel resource shapes.
- Prefer service-layer changes over pushing business logic into route handlers or React components.
- Be careful with inventory and accounting flows. Sales, refunds, receipts, and settlements have ledger side effects.
- Printer monitoring is operationally sensitive and reaches outside the app. Avoid touching it casually.
- The worktree may be clean now, but do not assume generated SQLite files are disposable unless you created them in this session.
- Treat GitHub issues as the source of truth for all work. Do not start or finish meaningful work without tying it to an issue.
- When asked to create an issue, use plan mode and produce a detailed, actionable issue with clear scope, constraints, acceptance criteria, and validation steps.
- Ask clarifying questions when requirements are materially ambiguous or the wrong assumption would create rework.
- Default to expert recommendations, but user direction overrides when explicitly provided.
- Before considering any issue complete, update affected repository documentation so it stays current and detailed.
- `web01.bengtson.local` is an available deployment target running this application. After implementation, testing, validation, and documentation updates are complete, deployment to `web01` may be performed to make changes live.
- Production on `web01` runs from `/srv/3d-print-sales/repo` using Docker Compose plus the server env file at `/srv/3d-print-sales/env/web01.env`.
- Canonical deploy entrypoints on `web01` are `scripts/web01-compose.sh up -d --build`, `systemctl reload 3d-print-sales.service`, or `/srv/3d-print-sales/deploy.sh` when a pull-and-rebuild deploy is intended.
- Before deploying, ensure the target commit/branch is correct on the server checkout and that required migrations, docs, tests, and validation are already complete.
- After deploying to `web01`, verify container health, backend health, and frontend reachability before calling the work live.

## Validation

- Backend tests: `python3 -m pytest backend/tests -q`
- Frontend build: `cd frontend && npm run build`
- If backend dependencies are missing locally, create a venv and install `backend/requirements.txt` first.
- Prefer targeted pytest runs while iterating, then rerun the broader relevant suite.
- All delivered work should include testing and validation appropriate to the change. Do not treat implementation alone as done.
- If work is intended to go live, complete local validation first, then verify deployment on `web01` with appropriate post-deploy checks.
- Standard post-deploy checks on `web01`:
- `cd /srv/3d-print-sales/repo && scripts/web01-compose.sh ps`
- `curl -fsS http://127.0.0.1/health`
- `curl -I http://127.0.0.1/`
- Review recent logs when the change affects startup, migrations, API routing, auth, printer monitoring, or frontend assets.

## Known Risks

- `backend/app/services/sales_service.py` generates `sale_number` from a yearly row count. That is race-prone under concurrent sale creation because the column is unique.
- `backend/app/services/printer_monitoring.py` is imported during app startup and depends on `websockets`; backend environments need that dependency installed or the app and tests will fail before collection.
- README coverage is broader than the minimum validated local setup. Verify routes and tests rather than relying on documentation alone.

## Expected Change Pattern

- Backend feature work usually means updating: model or migration, schema, service, endpoint, and tests.
- Frontend feature work usually means updating: API calls, route/page state, shared types, and loading/error handling.
- If a change touches sales, printers, inventory, or accounting, inspect existing tests first and extend them with the behavior change.

## Collaboration Notes

- Friendly, clear communication is preferred; light humor is fine when it does not get in the way.
- Thoroughness matters more than brevity for task execution, issue definition, validation, and documentation.
- Skills may be installed and used when they materially improve execution.
- Sub-agents may be used for implementation, research, or parallel investigation when helpful.

## Deployment Notes

- Live host: `root@web01.bengtson.local`
- App root on host: `/srv/3d-print-sales`
- Repo checkout on host: `/srv/3d-print-sales/repo`
- Server env file: `/srv/3d-print-sales/env/web01.env`
- Systemd unit: `3d-print-sales.service`
- Compose wrapper: `/srv/3d-print-sales/repo/scripts/web01-compose.sh`
- Helper deploy script: `/srv/3d-print-sales/deploy.sh`
- Running containers: `3d-print-sales-db`, `3d-print-sales-backend`, `3d-print-sales-frontend`
