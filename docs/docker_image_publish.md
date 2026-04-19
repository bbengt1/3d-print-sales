# Docker Image Publishing

This document is the source of truth for issue `#134`: how the repository builds and publishes Docker images in GitHub Actions, how tags work, and how those images relate to deployment.

## Published Images

The repository publishes two production images:

- `docker.io/<namespace>/print-backend`
- `docker.io/<namespace>/print-frontend`

Default namespace behavior:

- the workflow uses the repository variable `DOCKERHUB_NAMESPACE` when it is set
- otherwise it falls back to the GitHub repository owner name

For this repository, the practical default is currently `bbengt1` unless the GitHub variable overrides it.

## GitHub Actions Workflow

Workflow file:

- [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml)

Behavior:

- pull requests: build both production images, but do not push them
- pushes to `main`: build and push both images
- pushes to version tags matching `v*`: build and push both images
- manual dispatch: allowed, but image push still only happens from `main` or `v*` tags

This keeps pull requests as build-only validation while reserving Docker Hub publishing for approved refs.

## Required GitHub Configuration

Repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Repository variable:

- `DOCKERHUB_NAMESPACE`

`DOCKERHUB_TOKEN` should be a Docker Hub access token, not a password.

## Tagging And Promotion Strategy

The repository uses this baseline strategy:

- every publish gets an immutable `sha-<full-commit-sha>` tag
- pushes to `main` also publish the rolling `main` tag
- pushes to release tags such as `v1.2.3` publish:
  - the exact Git tag, for example `v1.2.3`
  - semver expansion tags such as `1.2.3` and `1.2`
  - the rolling `latest` tag

PR builds also compute `pr-<number>` metadata tags, but those builds are not pushed to Docker Hub.

This means:

- `sha-*` is the immutable traceable artifact tag
- `main` is the continuously updated integration tag
- `latest` is reserved for explicit release tags

## Current Consumption Model

Current `web01` production remains source-build oriented:

- `scripts/web01-compose.sh up -d --build` still rebuilds from the checked-out repository
- `docker-compose.prod.yml` is not yet switched to consume prebuilt Docker Hub images directly

That is deliberate for now. Issue `#134` establishes artifact publishing first. A later deployment automation step, such as issue `#135`, can choose whether to consume these published images directly.

## Operational Guidance

Use `sha-*` tags when traceability matters more than convenience.

Examples:

- safest explicit backend image reference: `docker.io/<namespace>/print-backend:sha-<full-commit-sha>`
- rolling integration reference: `docker.io/<namespace>/print-backend:main`
- release reference: `docker.io/<namespace>/print-backend:1.2.3`

Avoid deploying production from `latest` unless the environment intentionally tracks release tags without a stricter pin.

## Validation Expectations

Validation for this workflow should include:

- workflow YAML parses correctly
- PR builds complete without pushing
- pushes to `main` publish both images successfully
- a published `sha-*` image can be pulled explicitly
- the documented tags match what appears in Docker Hub
