# Reference Map

This is the authoritative technical reference index for the current codebase.

## Runtime And Configuration

- [`../getting_started.md`](../getting_started.md) - validated bootstrap flow for fresh local and `web01` installs
- [`../../.env.example`](../../.env.example) - development environment template
- [`../../.env.production.example`](../../.env.production.example) - production/server environment template
- [`../../scripts/bootstrap-env.sh`](../../scripts/bootstrap-env.sh) - generates usable env files from the tracked templates
- [`../../backend/app/core/config.py`](../../backend/app/core/config.py) - runtime configuration defaults, placeholder enforcement, and derived `DATABASE_URL` behavior

## Startup And Schema Behavior

- [`../../backend/app/main.py`](../../backend/app/main.py) - FastAPI app startup, lifespan, schema creation toggle, and health endpoint
- [`../../backend/app/seed.py`](../../backend/app/seed.py) - default seed data and admin-user bootstrap behavior
- [`../../backend/alembic.ini`](../../backend/alembic.ini) - Alembic configuration entry point
- [`../../backend/alembic/env.py`](../../backend/alembic/env.py) - migration environment wiring

## Containers And Deployment

- [`../../docker-compose.yml`](../../docker-compose.yml) - development compose stack
- [`../../docker-compose.prod.yml`](../../docker-compose.prod.yml) - production compose stack
- [`../../backend/Dockerfile`](../../backend/Dockerfile) - backend container build targets
- [`../../frontend/Dockerfile`](../../frontend/Dockerfile) - frontend container build targets
- [`../../scripts/web01-compose.sh`](../../scripts/web01-compose.sh) - canonical `web01` compose wrapper
- [`../docker_image_publish.md`](../docker_image_publish.md) - Docker Hub publishing model, tag strategy, and required GitHub secrets/variables

## CI And Repository Safeguards

- [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml) - baseline backend/frontend validation in GitHub Actions
- [`../../.github/workflows/docker-publish.yml`](../../.github/workflows/docker-publish.yml) - Docker Buildx workflow for build-only PR validation and Docker Hub publishing from approved refs
- [`../../.github/workflows/secret-scan.yml`](../../.github/workflows/secret-scan.yml) - gitleaks-based repository secret scan

## Maintained Docs Families

- [`../index.md`](../index.md) - task-oriented documentation hub
- `deployment_web01_*` docs - current `web01` deployment story
- finance and workflow docs under `docs/` - feature-area technical references that should stay aligned with code changes
