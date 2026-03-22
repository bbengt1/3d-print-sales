# Deployment Plan — web01.bengtson.local

## Goal

Deploy **3D Print Sales** to:
- `web01.bengtson.local`
- access path to be finalized during ingress setup

Deployment style:
- Docker / Docker Compose
- server-managed persistent storage
- documented, repeatable operations workflow

---

## Deployment Issue Map

### Epic
- #48 — Deploy 3D Print Sales to web01.bengtson.local with Docker

### Execution Order
1. #49 — Audit web01.bengtson.local and prepare Docker host prerequisites
2. #50 — Create production Docker Compose configuration for web01
3. #51 — Configure environment, secrets, and persistent storage for production deployment
4. #52 — Configure ingress for web01.bengtson.local (reverse proxy, hostname routing, and TLS strategy)
5. #53 — Execute first deployment to web01 and validate smoke tests
6. #54 — Document operations runbook for web01 deployment

---

## Proposed Rollout Strategy

## Phase A — Host Assessment

Purpose:
- verify server readiness before changing app config

Tasks:
- SSH into `root@web01.bengtson.local`
- capture OS/version/resources/disk/network baseline
- verify Docker Engine and Compose plugin presence
- identify existing reverse proxy/services/container conflicts
- confirm target deployment path on disk

Primary issue:
- #49

Deliverables:
- host baseline notes
- blocker list (if any)
- recommended deployment directory structure

Status:
- initial audit completed and documented in [docs/deployment_web01_audit.md](./deployment_web01_audit.md)
- current main blocker: Docker / Docker Compose not yet installed on the host

---

## Phase B — Production Container Definition

Purpose:
- make the repo runnable on a server without dev-only assumptions

Tasks:
- create/refine production compose file(s)
- define service boundaries:
  - backend
  - frontend
  - postgres
  - optional reverse proxy
- configure health checks and restart policies
- ensure persistent volumes are explicitly declared

Primary issue:
- #50

Deliverables:
- production Docker Compose configuration
- server-ready deployment commands

---

## Phase C — Secrets and Persistent Data

Purpose:
- keep production credentials out of git and preserve business data safely

Tasks:
- define `.env` / secrets injection workflow
- generate production-safe credentials/secrets
- define volume and backup-sensitive paths
- document required server-side files and permissions

Primary issue:
- #51

Deliverables:
- production env template/instructions
- persistent volume/storage plan
- secret-handling procedure

---

## Phase D — Ingress and Reachability

Purpose:
- make the app reachable in a predictable, documented way

Tasks:
- choose reverse proxy (Caddy/Nginx/Traefik)
- map hostname and ports
- define LAN-only vs externally reachable assumptions
- define TLS plan or explicitly document deferral

Primary issue:
- #52

Deliverables:
- ingress config
- access URL
- TLS/hostname notes

---

## Phase E — First Deployment

Purpose:
- prove the stack works end-to-end on the target host

Tasks:
- deploy stack to `web01`
- verify service health
- validate login, API access, and DB persistence
- capture any host-specific fixes during rollout

Primary issue:
- #53

Smoke tests:
- containers up and healthy
- frontend reachable
- API reachable
- admin login works
- data persists across restart
- basic app workflow succeeds

---

## Phase F — Runbook

Purpose:
- make the deployment maintainable after first launch

Tasks:
- document deploy/update flow
- document rollback approach
- document backup/restore approach
- document log and troubleshooting commands

Primary issue:
- #54

Deliverables:
- operations runbook in repo

---

## Open Questions To Resolve During Execution

1. Is this deployment LAN-only or intended for outside access later?
2. Which hostname should be canonical for end-user access?
3. Should images be built on-host or from prebuilt images?
4. Should Postgres run on the same host inside Compose, or is an external DB preferred?
5. What backup cadence is acceptable for app + database data?

---

## Definition of Success

The deployment planning effort is successful when:
- repo contains a server-ready deployment plan
- each deployment issue has a clear execution order
- deployment decisions are documented before host changes become ad hoc
- future execution on `web01.bengtson.local` can proceed step-by-step from repo docs + issues
