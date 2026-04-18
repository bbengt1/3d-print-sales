#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/bootstrap-env.sh local [--output PATH] [--admin-email EMAIL] [--force]
  scripts/bootstrap-env.sh web01 [--output PATH] [--admin-email EMAIL] [--force]

Modes:
  local   Generate a development .env from .env.example
  web01   Generate a server env file from .env.production.example

Examples:
  scripts/bootstrap-env.sh local
  scripts/bootstrap-env.sh web01 --output /srv/3d-print-sales/env/web01.env
EOF
}

mode=""
output=""
admin_email=""
force=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    local|web01)
      mode="$1"
      shift
      ;;
    --output|-o)
      output="${2:?missing output path}"
      shift 2
      ;;
    --admin-email)
      admin_email="${2:?missing admin email}"
      shift 2
      ;;
    --force|-f)
      force=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$mode" ]]; then
  usage >&2
  exit 1
fi

case "$mode" in
  local)
    template=".env.example"
    default_output=".env"
    ;;
  web01)
    template=".env.production.example"
    default_output="./web01.env"
    ;;
esac

output="${output:-$default_output}"

if [[ ! -f "$template" ]]; then
  echo "Missing template: $template" >&2
  exit 1
fi

if [[ -e "$output" && "$force" -ne 1 ]]; then
  echo "Refusing to overwrite existing file: $output" >&2
  echo "Re-run with --force if you want to replace it." >&2
  exit 1
fi

mkdir -p "$(dirname "$output")"

python3 - "$template" "$output" "$mode" "$admin_email" <<'PY'
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote
import sys

template_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
mode = sys.argv[3]
admin_email_override = sys.argv[4]

raw_lines = template_path.read_text().splitlines()
entries: list[tuple[str, str, str] | tuple[str, str]] = []
values: dict[str, str] = {}

for line in raw_lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        entries.append(("raw", line))
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    values[key] = value
    entries.append(("kv", key, value))

if admin_email_override:
    values["ADMIN_EMAIL"] = admin_email_override

values["DB_PASSWORD"] = token_urlsafe(18)
values["SECRET_KEY"] = token_urlsafe(48)
values["ADMIN_PASSWORD"] = token_urlsafe(18)

if "DATABASE_URL" in values:
    db_user = values.get("DB_USER", "printuser")
    db_name = values.get("DB_NAME", "printsales")
    db_password = quote(values["DB_PASSWORD"], safe="")
    db_host = "db"
    values["DATABASE_URL"] = (
        f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    )

rendered: list[str] = []
for entry in entries:
    if entry[0] == "raw":
        rendered.append(entry[1])
        continue
    _, key, _ = entry
    rendered.append(f"{key}={values[key]}")

output_path.write_text("\n".join(rendered) + "\n")
PY

echo "Generated $output from $template"

if [[ "$mode" == "local" ]]; then
  echo "Next step: docker compose up -d --build"
else
  echo "Next step: ENV_FILE=$output docker compose -f docker-compose.prod.yml up -d --build"
fi
