# Production Environment, Secrets, and Storage — web01

This document defines how production configuration and persistent data should be handled for 3D Print Sales on `web01.bengtson.local`.

## Goals

- keep production secrets out of git
- make the server-side env workflow explicit
- define persistent data locations and backup-sensitive paths
- reduce the chance of accidental credential leakage or data loss

---

## Server-Side Layout

Recommended base path:
- `/srv/3d-print-sales`

Recommended structure:
- `/srv/3d-print-sales/repo/` — checked-out application repo
- `/srv/3d-print-sales/env/` — server-side env files (not committed)
- `/srv/3d-print-sales/backups/` — backup outputs/archives
- `/srv/3d-print-sales/scripts/` — optional operational helper scripts

Docker-managed persistent volume:
- `3d_print_sales_postgres_data`

## Important Note About Persistence

The Postgres data directory is currently stored in a **named Docker volume**:
- `3d_print_sales_postgres_data`

That means the primary durable data is not in the git repo and not in a simple bind mount path by default.

If bind-mounted storage is preferred later, that can be changed in a future deployment task, but the current production compose definition expects the named volume.

---

## Environment File Workflow

### Checked-in template
Use:
- `.env.production.example`

### Recommended server-side real env file
Create on web01:
- `/srv/3d-print-sales/env/web01.env`

### Permissions
Recommended:
```bash
mkdir -p /srv/3d-print-sales/env
cp /srv/3d-print-sales/repo/.env.production.example /srv/3d-print-sales/env/web01.env
chmod 600 /srv/3d-print-sales/env/web01.env
```

If a dedicated deployment user is introduced later, ownership should be adjusted appropriately.

---

## Required Secret / Config Values

These values must be set with real production-safe values before deployment.
The backend refuses to start if tracked placeholder secrets are still present.

### Database
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`

### Application/Auth
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`

### App behavior
- `ENVIRONMENT=production`
- `TESTING=false`
- `BACKEND_CORS_ORIGINS`

### Admin seed
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

### Rate limiting
- `RATE_LIMIT_PER_MINUTE`
- `RATE_LIMIT_BURST`

---

## Secret Generation Guidance

### Database password
Use a strong random password.

Example generation:
```bash
openssl rand -base64 32
```

### SECRET_KEY
Use a long, random, unique value.

Example generation:
```bash
openssl rand -hex 64
```

### Admin password
Use a strong temporary password and rotate it if the seed account is used for first access.

---

## Launch Pattern

Use the server-side env file explicitly:

```bash
cd /srv/3d-print-sales/repo
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

This avoids relying on a local `.env` inside the repository checkout.

---

## Backup-Sensitive Data

### Critical
1. Docker volume:
   - `3d_print_sales_postgres_data`
2. server-side env file:
   - `/srv/3d-print-sales/env/web01.env`

### Important but reproducible
1. checked-out repo copy:
   - `/srv/3d-print-sales/repo/`
2. deployment docs / scripts under `/srv/3d-print-sales/`

### Backup recommendation
At minimum, back up:
- the Postgres volume contents (or DB dump)
- the production env file

---

## Suggested Backup Approach

### Database dump example
```bash
docker exec 3d-print-sales-db pg_dump -U "$DB_USER" "$DB_NAME" > /srv/3d-print-sales/backups/printsales-$(date +%F).sql
```

### Volume-level awareness
If you prefer full-volume backups, document and test restore steps before relying on them in production.

### Retention
Initial recommended baseline:
- daily DB dump
- keep 7 daily backups
- keep 4 weekly backups

This can be adjusted later based on actual app usage and acceptable recovery point objectives.

---

## Things That Must NOT Be Committed

Do not commit any of the following:
- real `web01.env`
- real production passwords
- real JWT/secret keys
- backup files
- DB dumps

---

## Operational Checks Before Deployment

Before first deployment, verify:
- `/srv/3d-print-sales/env/web01.env` exists
- permissions on the env file are restricted
- real secret values have replaced all placeholder values
- backup directory exists
- operator knows where persistent DB data lives

---

## Related Files

- `.env.production.example`
- `docker-compose.prod.yml`
- `docs/deployment_web01_plan.md`
- `docs/deployment_web01_compose.md`
- `docs/deployment_web01_audit.md`
