#!/usr/bin/env bash
# Canonical deploy script for web01.
#
# Runs the full deploy sequence:
#   1. Pull latest main from origin (fast-forward only).
#   2. Bring containers up with --build (rebuilds backend/frontend images).
#   3. Run pending Alembic migrations against the live DB. THIS IS REQUIRED:
#      backend startup queries tables/columns added by recent migrations, so
#      forgetting this step will crash the backend container after a deploy
#      that adds schema. (Real incident on 2026-05-09 with PR #271 / #239.)
#
# Designed to be invoked from `/srv/3d-print-sales/deploy.sh` on web01:
#   /srv/3d-print-sales/deploy.sh
# That host script is a thin wrapper that cd's into the repo and calls this.
#
# Idempotent: re-running with no new commits is a no-op for git, a quick
# rebuild check for compose, and a no-op for alembic (already at head).
#
# To skip migrations explicitly (rare — e.g. pre-flight a code-only deploy),
# set SKIP_MIGRATIONS=1 in the environment.

set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/3d-print-sales/repo}"
COMPOSE="$REPO_DIR/scripts/web01-compose.sh"

cd "$REPO_DIR"

echo "==> [1/3] git pull --ff-only"
git pull --ff-only

echo "==> [2/3] compose up -d --build"
"$COMPOSE" up -d --build

if [[ "${SKIP_MIGRATIONS:-0}" == "1" ]]; then
  echo "==> [3/3] migrations SKIPPED (SKIP_MIGRATIONS=1 set)"
else
  echo "==> [3/3] alembic upgrade head"
  "$COMPOSE" run --rm backend alembic upgrade head
  echo "==> migrations applied; restarting backend to pick up schema"
  "$COMPOSE" up -d backend
fi

echo "==> done. containers:"
"$COMPOSE" ps
