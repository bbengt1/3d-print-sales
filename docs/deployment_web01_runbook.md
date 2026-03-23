# Operations Runbook — web01.bengtson.local

This runbook covers routine operations for the 3D Print Sales deployment on `web01.bengtson.local`.

## Environment Summary

Host:
- `root@web01.bengtson.local`

App path:
- `/srv/3d-print-sales/repo`

Env file:
- `/srv/3d-print-sales/env/web01.env`

Backups path:
- `/srv/3d-print-sales/backups`

Compose file:
- `docker-compose.prod.yml`

Canonical URL:
- `http://web01.bengtson.local/`

---

## Services

Current production stack:
- `3d-print-sales-db`
- `3d-print-sales-backend`
- `3d-print-sales-frontend`

Named Docker volume:
- `3d_print_sales_postgres_data`

---

## Initial Deploy / Re-Deploy

### Standard deploy command
```bash
ssh root@web01.bengtson.local
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

### Required migration step
Production should be migration-driven, not `create_all()`-driven.

After updating code and before relying on new endpoints/models, run:

```bash
ssh root@web01.bengtson.local
cd /srv/3d-print-sales/repo/backend
python3 - <<'PY'
from urllib.parse import quote
import os, subprocess
user = os.environ.get('DB_USER', 'printuser')
password = quote(os.environ['DB_PASSWORD'], safe='')
db = os.environ.get('DB_NAME', 'printsales')
host = os.environ.get('DB_HOST', 'db')
port = os.environ.get('DB_PORT', '5432')
os.environ['DATABASE_URL'] = f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}'
subprocess.run(['docker', 'exec', '3d-print-sales-backend', 'alembic', 'upgrade', 'head'], check=True)
PY
```

### What this does
- uses the server-side env file
- rebuilds images from the checked-out repo
- starts or updates the stack in detached mode
- applies schema changes through Alembic instead of relying on runtime table creation

---

## Routine Update Procedure

```bash
ssh root@web01.bengtson.local
cd /srv/3d-print-sales/repo
git pull --ff-only
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

### Post-update checks
```bash
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1/health
curl -I http://127.0.0.1/
```

---

## Health Checks / Smoke Tests

### On-host
```bash
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml ps

curl -fsS http://127.0.0.1/health
curl -I http://127.0.0.1/
```

### Over hostname
```bash
curl -I http://web01.bengtson.local/
curl -fsS http://web01.bengtson.local/health
```

### Login smoke test
Use the browser or scripted login against:
- `http://web01.bengtson.local/api/v1/auth/login`

---

## Logs and Troubleshooting

### Compose service status
```bash
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml ps
```

### Tail all logs
```bash
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml logs -f
```

### Tail individual services
```bash
docker logs -f 3d-print-sales-db
docker logs -f 3d-print-sales-backend
docker logs -f 3d-print-sales-frontend
```

### Common quick checks
```bash
systemctl status docker
firewall-cmd --list-all
ss -tulpn | grep -E ':80|:9090|:22'
docker volume ls | grep 3d_print_sales_postgres_data
```

---

## Restart Operations

### Restart one service
```bash
docker restart 3d-print-sales-backend
docker restart 3d-print-sales-frontend
docker restart 3d-print-sales-db
```

### Restart whole stack
```bash
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml restart
```

---

## Rollback Approach

### Fast rollback to previous git revision
If a new deployment is bad but the previous code revision is known:

```bash
ssh root@web01.bengtson.local
cd /srv/3d-print-sales/repo
git log --oneline -n 10
# choose prior known-good commit
git checkout <known-good-commit>
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

### After rollback
- verify compose health
- verify `/health`
- verify browser access
- record what commit was rolled back to

### Important note
If you use a detached commit for rollback, remember to return the repo to the desired branch later.

---

## Backup Procedure

### Database dump
```bash
ssh root@web01.bengtson.local
source /etc/profile >/dev/null 2>&1 || true
DB_USER=$(awk -F= '/^DB_USER=/{print $2}' /srv/3d-print-sales/env/web01.env)
DB_NAME=$(awk -F= '/^DB_NAME=/{print $2}' /srv/3d-print-sales/env/web01.env)
mkdir -p /srv/3d-print-sales/backups

docker exec 3d-print-sales-db pg_dump -U "$DB_USER" "$DB_NAME" \
  > /srv/3d-print-sales/backups/printsales-$(date +%F-%H%M%S).sql
```

### What to retain
Critical backup items:
- DB dump(s)
- `/srv/3d-print-sales/env/web01.env`

### Suggested retention baseline
- 7 daily backups
- 4 weekly backups

---

## Restore Procedure

### Restore database from SQL dump
```bash
ssh root@web01.bengtson.local
DB_USER=$(awk -F= '/^DB_USER=/{print $2}' /srv/3d-print-sales/env/web01.env)
DB_NAME=$(awk -F= '/^DB_NAME=/{print $2}' /srv/3d-print-sales/env/web01.env)

cat /srv/3d-print-sales/backups/<backup-file>.sql \
  | docker exec -i 3d-print-sales-db psql -U "$DB_USER" "$DB_NAME"
```

### Caution
Only restore into the active DB when you are certain that is intended. For safer recovery testing, restore into a temporary database/container first.

---

## Secrets / Env Changes

### Edit env file
```bash
vi /srv/3d-print-sales/env/web01.env
chmod 600 /srv/3d-print-sales/env/web01.env
```

### Apply env changes
```bash
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

---

## Firewall / Access Notes

Current ingress expectations:
- app served on port `80/tcp`
- SSH on `22/tcp`
- `9090/tcp` reserved by existing host service (likely Cockpit)

If HTTP access stops working, check:
```bash
firewall-cmd --list-all
ss -tulpn | grep ':80'
```

---

## Known Deployment Notes

- Current deployment is HTTP-only and LAN-oriented.
- TLS is intentionally deferred for now.
- Frontend nginx is the current ingress point and proxies API traffic internally.
- Correct health endpoint is `/health`, not `/api/v1/health`.

---

## When to Escalate / Revisit Design

Consider revisiting the deployment architecture if:
- external/public access is required
- HTTPS becomes mandatory
- multiple apps need to share the host cleanly
- backup/restore needs stricter RPO/RTO guarantees
- image build times on-host become a problem

At that point, likely next improvements are:
- dedicated reverse proxy (Caddy/Nginx/Traefik)
- scheduled DB backups
- prebuilt images / CI-based deploy flow
- monitoring/alerting
