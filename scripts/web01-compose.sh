#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

: "${ENV_FILE:=/srv/3d-print-sales/env/web01.env}"
: "${FRONTEND_HTTP_PORT:=80}"
export ENV_FILE FRONTEND_HTTP_PORT

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing ENV_FILE: $ENV_FILE" >&2
  exit 1
fi

cd "$REPO_DIR"
exec docker compose -f docker-compose.prod.yml "$@"
