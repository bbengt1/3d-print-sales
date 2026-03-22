# Ingress Strategy — web01.bengtson.local

This document defines the initial ingress and hostname-routing approach for running 3D Print Sales on `web01.bengtson.local`.

## Decision

For the **initial deployment**, the ingress strategy is:
- use the **frontend nginx container** as the first HTTP entry point
- publish container port 80 to host port 80
- use `web01.bengtson.local` as the canonical access hostname
- treat the initial deployment as **LAN/local-network oriented**
- **defer TLS** until there is a clear need for public exposure or a dedicated certificate strategy

This keeps the first deployment simple and consistent with the current Compose layout.

---

## Access URL

Canonical initial URL:
- `http://web01.bengtson.local/`

API path:
- `http://web01.bengtson.local/api/v1/...`

Health path:
- `http://web01.bengtson.local/health`

---

## Current Routing Shape

### Frontend ingress
The frontend production container runs nginx and:
- serves the SPA
- proxies `/api/` requests to the backend container
- proxies `/health` to the backend health endpoint

### Server name
The nginx config recognizes:
- `web01.bengtson.local`
- fallback `_`

---

## Hostname Assumptions

This plan assumes the hostname `web01.bengtson.local` resolves correctly on the network where the app will be accessed.

Possible resolution options:
- local DNS already resolves `web01.bengtson.local`
- router/DNS server manages local name resolution
- client hosts file entry if necessary during testing

If local DNS is not already in place, a temporary hosts entry can be used:

```text
10.0.1.43  web01.bengtson.local
```

---

## Firewall / Port Expectations

Expected host port for first deployment:
- `80/tcp`

Expected currently reserved ports to avoid:
- `22/tcp` (SSH)
- `9090/tcp` (existing host service, likely Cockpit-related)

Because `firewalld` is active on web01, port 80 will need to be opened during deployment execution.

---

## TLS Strategy

### Current decision
TLS is **intentionally deferred** for the first LAN-oriented deployment.

### Why
- this is an internal/local hostname deployment
- there is not yet a finalized public DNS/certificate strategy
- keeping the initial rollout HTTP-only reduces moving parts while we prove the app stack on the target host

### Future upgrade path
If/when public or stronger internal HTTPS access is required, recommended next step is to introduce a dedicated reverse proxy under a future deployment task, such as:
- Caddy
- Nginx
- Traefik

At that point we can:
- terminate TLS at the proxy
- forward traffic to the frontend/backend stack
- support certificates and redirects cleanly

---

## Smoke-Test Expectations

Once deployment is live, basic ingress smoke tests should use:
- `http://web01.bengtson.local/`
- `http://web01.bengtson.local/health`
- app login through the same hostname

Expected behavior:
- homepage loads
- frontend routes work
- API requests succeed through nginx proxying
- no direct backend port exposure is required for normal browser access

---

## Related Files

- `frontend/nginx.conf`
- `docker-compose.prod.yml`
- `docs/deployment_web01_plan.md`
- `docs/deployment_web01_compose.md`
- `docs/deployment_web01_env_and_storage.md`
