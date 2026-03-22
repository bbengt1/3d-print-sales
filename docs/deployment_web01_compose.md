# Production Docker Compose Notes for web01

This document describes the current production deployment shape for running 3D Print Sales on `web01.bengtson.local`.

## Files

- `docker-compose.prod.yml`
- `.env.production.example`

## Services

### db
- image: `postgres:16-alpine`
- persistent volume: `3d_print_sales_postgres_data`
- internal-only service on the compose network
- health check via `pg_isready`

### backend
- built from `backend/Dockerfile` production target
- reads environment via `env_file`
- connects to the internal Postgres service
- health check against `http://127.0.0.1:8000/health`

### frontend
- built from `frontend/Dockerfile` production target
- serves the built SPA through nginx
- proxies `/api/` to the backend container
- publishes HTTP on `${FRONTEND_HTTP_PORT:-80}`
- health check against local HTTP root

## Network

- one internal bridge network: `app_net`

## Volumes

- `3d_print_sales_postgres_data`

## Expected Server-Side Env File

Recommended location on `web01`:
- `/srv/3d-print-sales/env/web01.env`

You can start from:
- `.env.production.example`

## Example Launch

```bash
cd /srv/3d-print-sales/repo
cp .env.production.example /srv/3d-print-sales/env/web01.env
# edit secrets before launch

ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

## Example Update

```bash
cd /srv/3d-print-sales/repo
git pull --ff-only
ENV_FILE=/srv/3d-print-sales/env/web01.env \
FRONTEND_HTTP_PORT=80 \
  docker compose -f docker-compose.prod.yml up -d --build
```

## Notes

- This configuration is production-oriented and does not use the development bind mounts from `docker-compose.yml`.
- Reverse proxy/TLS decisions may further evolve under issue #52.
- The current frontend container can serve as the first ingress point on port 80 until a dedicated reverse proxy is introduced.
