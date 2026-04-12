# Claude Code Configuration

## Primary Working Guide

**Read and follow `agents.md` in the repo root.** It is the authoritative source for:
- Repository map and architecture
- Working rules and collaboration style
- Validation commands and expected change patterns
- UX laws for frontend work
- Documentation standards
- Commit, PR, and deployment guidelines
- Known risks and operational sensitivities

## Quick Reference

### Validation Commands
- Backend tests: `python3 -m pytest backend/tests -q`
- Frontend build: `cd frontend && npm run build`

### Key Rules
- Treat GitHub issues as the source of truth for all work.
- Keep API, schema, model, and frontend type changes in sync.
- Prefer service-layer changes over business logic in route handlers or React components.
- Inventory, accounting, sales, and printer monitoring are operationally sensitive — inspect existing tests first.
- Every completed task includes explicit validation and documentation updates.
- When creating issues, use plan mode and produce detailed, actionable user stories.
- Default to test-driven development when practical.
- Ask clarifying questions when requirements are materially ambiguous.

### Deployment
- Live host: `root@web01.bengtson.local`
- App root: `/srv/3d-print-sales`
- Deploy: `scripts/web01-compose.sh up -d --build` or `/srv/3d-print-sales/deploy.sh`
- Post-deploy checks: container health, `curl /health`, `curl /`, review logs if relevant.
