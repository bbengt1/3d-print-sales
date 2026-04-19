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

## Working Style
- Work is tracked and driven through GitHub issues. Prefer starting from an issue, implementing against that issue, and closing the loop in the issue or linked PR instead of treating chat alone as the source of truth.
- When creating or refining issues, use Plan mode and write a detailed, actionable user story. The body should include the user problem, scope, acceptance criteria, and concrete implementation guidance with examples across code, UI, data, and testing.
- Default to test-driven development when practical: outline the expected behavior first, add or update tests close to the change, then implement until the tests pass. If strict TDD is not practical for a slice, still add validation coverage before calling the work done.
- Every completed task should include explicit validation. Run the relevant commands, smoke tests, or manual verification steps and capture what was validated.
- Before marking work complete, update any impacted repository documentation so it stays accurate, detailed, and current. This includes `README.md`, `docs/`, runbooks, deployment notes, env docs, and feature-specific documentation whenever behavior or workflows change.
- Sub-agents may be used when they improve quality or speed, especially for bounded research, implementation, or testing work. Use them deliberately, keep scopes narrow, and integrate the results rather than duplicating effort.
- Collaboration tone should stay friendly, calm, and thorough. A little humor is welcome when it helps, but the work product should still be crisp, complete, and dependable.

## UX Laws For Frontend Work
- Treat UX laws as strong heuristics, not rigid commandments. When laws conflict, prioritize task clarity, accessibility, and operational speed.
- Aesthetic-Usability Effect: visual polish matters because users perceive polished interfaces as easier to use, but do not let attractive styling hide weak information architecture or broken flows.
- Doherty Threshold: acknowledge user actions within roughly `400ms` when practical. If real work will take longer, show immediate feedback with optimistic state changes, skeletons, spinners, or progress indicators.
- Fitts's Law: keep primary and frequent actions large, close, and easy to hit. Avoid tiny icon-only controls, especially in dense operational tables and mobile layouts.
- Hick's Law: reduce the number and complexity of choices shown at once. Prefer progressive disclosure, sensible defaults, recommended actions, and chunked workflows over dumping every option on screen.
- Jakob's Law: default to familiar interface patterns unless there is a strong product reason not to. Novel UI is acceptable only when it meaningfully improves the task and still provides clear cues.
- Law of Common Region, Law of Proximity, Law of Similarity, and Law of Uniform Connectedness: use spacing, containers, repeated styling, and visible connections to make relationships obvious. Do not rely on color alone to imply grouping.
- Law of Prägnanz: simplify layouts until the intended structure is obvious at a glance. Favor clean hierarchy, clear grouping, and low visual noise over decorative complexity.
- Miller's Law: chunk information so users do not have to hold too much in working memory. Do not treat `7 +/- 2` as a hard UI limit or as an excuse for arbitrary navigation/menu rules.
- Occam's Razor: prefer the simplest interaction model that still solves the real problem. Every new control, panel, filter, or modal should justify its existence.
- Pareto Principle: optimize the highest-frequency workflows and the biggest pain points first. The most used `20%` of the interface usually deserves the most design, testing, and polish attention.
- When proposing or reviewing frontend changes, name the relevant law or tradeoff when it helps explain why a design decision is better, faster, or easier to learn.
- Reviewed for this repo on `2026-04-08` against the Laws of UX reference set and related articles, including:
  - `https://lawsofux.com/laws/`
  - `https://lawsofux.com/doherty-threshold/`
  - `https://lawsofux.com/jakobs-law/`
  - `https://lawsofux.com/law-of-common-region/`
  - `https://lawsofux.com/law-of-pr%C3%A4gnanz/`
  - `https://lawsofux.com/law-of-proximity/`
  - `https://lawsofux.com/law-of-similarity/`
  - `https://lawsofux.com/law-of-uniform-connectedness/`
  - `https://lawsofux.com/millers-law/`
  - `https://lawsofux.com/pareto-principle/`
  - `https://lawsofux.com/articles/2018/the-psychology-of-design/`

## Documentation UX And Freshness
- Treat documentation as a product surface. Docs should help readers orient quickly, build the right mental model, and find the authoritative answer without hunting through overlapping files.
- Keep the documentation entry points aligned:
  - `README.md` is the repo-root orientation layer.
  - `docs/index.md` is the main audience and task-based documentation hub.
  - `docs/reference/index.md` is the authoritative technical reference map tied to the current codebase.
  - `docs/README.md` is only a compatibility pointer for older links and should not become a competing hub.
- Apply the UX laws to documentation structure:
  - Hick's Law: reduce competing entry points and avoid too many equal-weight navigation choices.
  - Jakob's Law: use familiar documentation patterns such as overview, quick start, architecture, workflows, troubleshooting, and reference.
  - Law of Prägnanz plus Common Region / Proximity / Similarity / Uniform Connectedness: make structure obvious with clean sections, grouped links, tables, and clear document families.
  - Miller's Law: chunk long explanations into short sections, diagrams, tables, and step-by-step flows.
  - Occam's Razor and Pareto Principle: optimize the docs for the most common questions first and do not add extra prose when a diagram, table, or shorter explanation would be clearer.
- Prefer editable visuals for relationship-heavy concepts:
  - use `mermaid` directly in markdown when practical
  - use source-controlled SVG assets in `docs/assets/` when more layout control is needed
  - avoid non-editable screenshots unless a real UI capture is the point
- When behavior changes affect architecture, request flow, auth/session flow, deployment topology, feature-area maps, or workflow understanding, update the related diagrams and visual assets in the same change.
- Mark source-of-truth status clearly. If a document is historical, contextual, or legacy-oriented, label it so readers do not mistake it for the maintained reference path.
- Keep major docs structurally consistent when practical:
  - purpose / audience
  - quick summary or start-here guidance
  - main content
  - validation / verification or troubleshooting when relevant
  - related docs
- Before calling documentation work complete, validate the documentation itself:
  - verify internal markdown links and asset references
  - review diagrams for accuracy against the current codebase
  - make sure updated docs still align with the intended docs information architecture and source-of-truth model

  ## Commit & Pull Request Guidelines
- Commits: concise, present-tense summaries (e.g., `feat: add incident filter`, `fix: tighten auth middleware`). Group related changes.
- PRs: include context, linked ticket, and key commands run. Note API contract, route, feature-flag, or schema changes and update OpenAPI, docs, and UI consumers together. Attach screenshots or sample JSON for UI/endpoint changes; list env vars or workflow inputs touched. If documentation changed as part of the work, call that out explicitly in the PR summary.

## Deployment Notes

- **Canonical deploy path: the `web01-deploy` n8n workflow** defined at [`ops/n8n/web01-deploy.json`](ops/n8n/web01-deploy.json). It encapsulates the full deploy sequence (pull → migrate → rebuild → verify) with per-step observability. Operator runbook: [`docs/deployment_n8n_workflow.md`](docs/deployment_n8n_workflow.md).
- **Fallback: the manual SSH flow below.** Use it when n8n is unavailable, when debugging a broken deploy, or when performing one-off operations that don't fit the workflow (e.g. `alembic downgrade`, emergency restart).
- Live host: `root@web01.bengtson.local`
- App root on host: `/srv/3d-print-sales`
- Repo checkout on host: `/srv/3d-print-sales/repo`
- Server env file: `/srv/3d-print-sales/env/web01.env`
- Systemd unit: `3d-print-sales.service`
- Compose wrapper: `/srv/3d-print-sales/repo/scripts/web01-compose.sh`
- Helper deploy script: `/srv/3d-print-sales/deploy.sh`
- Running containers: `3d-print-sales-db`, `3d-print-sales-backend`, `3d-print-sales-frontend`
