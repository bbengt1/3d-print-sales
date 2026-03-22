# web01.bengtson.local Deployment Audit

Audit date:
- 2026-03-21

Target host:
- `root@web01.bengtson.local`
- hostname: `web01.bengtson.local`
- primary IPv4: `10.0.1.43`

## Summary

`web01.bengtson.local` looks like a clean, lightly used host that is suitable for deploying 3D Print Sales.

### Key finding
The main blocker is simple:
- **Docker is not installed**
- **Docker Compose is not installed**

Everything else looks reasonable for proceeding once the Docker host setup is completed.

---

## System Baseline

### OS
- Rocky Linux 10.1

### Resources
- CPU: 4 cores
- Memory: ~3652 MB
- Root disk: 70 GB total / ~67 GB available

### Existing listening services
- SSH on port 22
- service bound to port 9090 (owned by `systemd`, likely Cockpit socket activation)

### Existing containers
- none

### Existing likely deployment paths
- `/srv` exists and is effectively empty
- recommended deployment path created/verified:
  - `/srv/3d-print-sales`

---

## Docker Readiness

### Current state
- `docker` command not present
- `docker compose` not present
- `docker-compose` not present

### Implication
Issue #50 and later deployment work are blocked until the host is prepared under issue #49.

### Recommended direction
- install Docker Engine
- install Docker Compose plugin
- validate service startup and enable on boot

---

## Networking / Access / Security Context

### Firewalld
- active
- default zone: `public`
- allowed services currently include:
  - `cockpit`
  - `dhcpv6-client`
  - `ssh`

No custom app ports are currently open.

### SELinux
- `Enforcing`

### Implication
Production deployment should assume:
- firewall rules will need to be explicitly opened for any chosen ingress ports
- SELinux-aware volume and container handling may be required if bind mounts are used

---

## Port Considerations

### Confirmed open/listening
- `22/tcp` — SSH
- `9090/tcp` — owned by `systemd` (likely Cockpit-related)

### Recommendation
Avoid reusing:
- `22`
- `9090`

Likely candidates for app ingress later:
- `80`
- `443`
- or internal app ports proxied behind a reverse proxy

---

## Recommended Server Layout

Suggested deployment root:
- `/srv/3d-print-sales`

Suggested structure:
- `/srv/3d-print-sales/compose/`
- `/srv/3d-print-sales/env/`
- `/srv/3d-print-sales/data/postgres/`
- `/srv/3d-print-sales/backups/`

This should be finalized during the production compose/secrets tasks.

---

## Blockers

### Blocking
1. Docker Engine not installed
2. Docker Compose plugin not installed

### Non-blocking but important
1. Firewalld is active and must be considered during ingress setup
2. SELinux is enforcing and must be considered for bind mounts/volumes
3. Port 9090 is already in use and should be left alone

---

## Recommended Next Issue

Proceed to:
- **#50** if Docker host preparation is handled as part of the deployment compose task

Or, more cleanly:
- finish the prerequisite/install work under **#49**, then move to **#50**

## Practical next actions
1. Install Docker Engine
2. Install Docker Compose plugin
3. Enable/start Docker service
4. Validate `docker ps` and `docker compose version`
5. Then move on to production compose implementation
