#!/usr/bin/env bash
# Canonical deploy script for web01.
#
# Order matters. The fix below is the result of two real incidents:
#   - 2026-05-09 (PR #271 / #239): forgetting `alembic upgrade head` crashed
#     the backend because new code queried not-yet-created tables.
#   - 2026-05-10 (PR #353 / #230): bringing all containers up with --build
#     before running alembic crashed the backend on startup, which then
#     failed the dependency healthcheck and aborted the whole `up`.
#
# Sequence:
#   1. Pull latest main from origin (fast-forward only).
#   2. Build images and start the DB.
#   3. Run pending Alembic migrations against the live DB. (Don't start
#      the backend yet — its startup may query columns that this migration
#      is creating.)
#   4. Bring backend + frontend up. Backend can now start cleanly.
#
# To skip migrations explicitly (rare — e.g. pre-flight a code-only deploy
# with no schema changes), set SKIP_MIGRATIONS=1 in the environment.

set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/3d-print-sales/repo}"
COMPOSE="$REPO_DIR/scripts/web01-compose.sh"

cd "$REPO_DIR"

echo "==> [1/4] git pull --ff-only"
git pull --ff-only

echo "==> [2/4] build images + start DB"
"$COMPOSE" build
"$COMPOSE" up -d db
"$COMPOSE" exec -T db sh -c 'until pg_isready -q -U "${POSTGRES_USER:-printuser}"; do sleep 1; done' || true

if [[ "${SKIP_MIGRATIONS:-0}" == "1" ]]; then
  echo "==> [3/4] migrations SKIPPED (SKIP_MIGRATIONS=1 set)"
else
  echo "==> [3/4] alembic upgrade head"
  "$COMPOSE" run --rm backend alembic upgrade head
fi

echo "==> [4/4] start backend + frontend"
"$COMPOSE" up -d

echo "==> done. containers:"
"$COMPOSE" ps
