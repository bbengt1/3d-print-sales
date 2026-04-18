# 3D Print Sales

Full-stack web application for managing a 3D printing business — job costing, pricing, material tracking, and business analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16 |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, Zustand |
| **Auth** | JWT (python-jose) + bcrypt |
| **API Docs** | OpenAPI 3.1 / Swagger UI |
| **Infrastructure** | Docker Compose, multi-stage builds, nginx (production) |

## Quick Start

```bash
# Clone and start (development)
git clone <repo-url>
cd 3d-print-sales
./scripts/bootstrap-env.sh local
docker compose up -d --build

# Services
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# Swagger:   http://localhost:8000/api/v1/docs
# ReDoc:     http://localhost:8000/api/v1/redoc
```

If you prefer to set values manually, copy `.env.example` to `.env` and replace the tracked placeholder secrets before first run.

### Production Deployment

```bash
# Generate a server env file, then point compose at it
./scripts/bootstrap-env.sh web01 --output /srv/3d-print-sales/env/web01.env
docker compose -f docker-compose.prod.yml up -d --build

# Access at http://localhost
```

### Admin Seed Login

The backend seeds an admin user from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. Set those values in your local `.env` before first run. The backend now refuses to start while tracked placeholder secrets remain in place.

### Start Here

- [Fresh Start Guide](docs/getting_started.md) - validated local bootstrap and `web01` deployment path
- [Docs Hub](docs/index.md) - task-oriented documentation entry point
- [Reference Map](docs/reference/index.md) - authoritative technical reference index

## Project Structure

```
3d-print-sales/
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── api/v1/        # REST endpoints (auth, settings, materials, rates, customers, jobs, products, inventory, sales, dashboard)
│   │   ├── core/          # Config, database, security
│   │   ├── middleware/     # Rate limiting
│   │   ├── models/        # SQLAlchemy models (11 tables)
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Cost calculation, inventory, sales, report engines
│   │   ├── seed.py        # Database seed data
│   │   └── main.py        # App entry point
│   ├── alembic/           # Database migrations
│   ├── Dockerfile         # Multi-stage (development/production)
│   └── requirements.txt
├── frontend/              # React + TypeScript application
│   ├── src/
│   │   ├── api/           # Axios API client
│   │   ├── components/    # Layout, UI (Skeleton, EmptyState, ErrorBoundary)
│   │   ├── pages/         # Route pages (Dashboard, Jobs, Materials, Rates, etc.)
│   │   ├── store/         # Zustand auth store
│   │   ├── types/         # TypeScript interfaces
│   │   └── lib/           # Utilities
│   ├── nginx.conf         # Production nginx config
│   ├── Dockerfile         # Multi-stage (development/build/production)
│   └── package.json
├── docker-compose.yml          # Development environment
├── docker-compose.prod.yml     # Production environment
├── .env.example
└── IMPLEMENTATION_PLAN.md
```

## API Endpoints

All endpoints are under `/api/v1`. Rate limited at 120 requests/minute per IP.

| Resource | Endpoints | Filters |
|----------|-----------|---------|
| **Auth** | `POST /auth/login`, `GET /auth/me`, `PUT /auth/me/password`, `POST /auth/register` (admin), `GET/PUT/DELETE /auth/users` (admin) | `?is_active` |
| **Settings** | `GET/PUT /settings`, `GET/PUT /settings/{key}`, `PUT /settings/bulk` | Admin-only |
| **Insights** | `GET /insights/status`, `POST /insights/summary` | Auth required |
| **Materials** | Full CRUD at `/materials` | `?active`, `?search`, pagination |
| **Rates** | Full CRUD at `/rates` | `?active`, pagination |
| **Customers** | Full CRUD at `/customers` | `?search` (name/email), pagination |
| **Jobs** | Full CRUD at `/jobs`, `POST /jobs/calculate` | `?status`, `?material_id`, `?customer_id`, `?date_from`, `?date_to`, `?search`, `?sort_by`, `?sort_dir`, pagination |
| **Products** | Full CRUD at `/products` | `?is_active`, `?material_id`, `?low_stock`, `?search`, pagination |
| **Cameras** | Full CRUD at `/cameras`, `POST /cameras/{id}/assign`, `GET /cameras/{id}/snapshot` | `?is_active`, `?assigned`, `?search`, pagination |
| **Inventory** | `GET/POST /inventory/transactions`, `GET /inventory/alerts` | `?product_id`, `?type`, pagination |
| **Sales Channels** | Full CRUD at `/sales/channels` | `?is_active` |
| **Sales** | Full CRUD at `/sales`, `GET /sales/metrics`, `GET /sales/{id}/shipping-label`, `POST /sales/{id}/shipping-label/mark-printed`, `POST /sales/{id}/refund`, `POST /pos/checkout`, `POST /pos/scan/resolve` | `?status`, `?channel_id`, `?payment_method`, `?customer_id`, `?date_from`, `?date_to`, `?search`, pagination |
| **Reports** | `GET /reports/inventory`, `/reports/sales`, `/reports/pl` + CSV variants | `?date_from`, `?date_to`, `?channel_id`, `?payment_method`, `?period` (daily/weekly/monthly/yearly) |
| **Dashboard** | `GET /dashboard/summary`, `/charts/revenue`, `/charts/materials`, `/charts/profit-margins` | `?date_from`, `?date_to` |

## Database

Twelve tables (6 seeded from the original spreadsheet + 2 for inventory + 3 for sales + 1 for cameras):

- **settings** — Business configuration (currency, margins, fees, electricity rates)
- **materials** — Filament inventory (PLA, PETG, TPU, ABS, PLA+) with cost-per-gram, spool stock tracking
- **rates** — Labor rate ($25/hr), machine rate ($1.50/hr), overhead (10%)
- **customers** — Customer contact information
- **jobs** — Full job tracking with 17 computed cost/pricing fields, optional product link
- **users** — Admin authentication
- **products** — Product catalog with auto-generated SKU, optional UPC, stock tracking, reorder points
- **inventory_transactions** — Stock movement ledger (production, sale, adjustment, return, waste)
- **sales_channels** — Sales platforms (Etsy, Amazon, Direct) with platform fee % and fixed fee per order
- **sales** — Order tracking with auto-generated sale number (S-YYYY-NNNN), status flow, computed totals and contribution margin
- **sale_items** — Line items per sale linking to products/jobs with quantity, pricing, and cost
- **cameras** — Camera devices (Wyze/go2rtc) with stream config, optional 1:1 printer assignment, snapshot proxy

## Cost Calculation Engine

Replicates the spreadsheet formulas server-side:

```
Electricity = (watts/1000) * print_hours * electricity_rate
Material    = grams_per_plate * plates * cost_per_g
Labor       = (labor_mins/60) * labor_rate
Machine     = print_hours * machine_rate
Subtotal    = all costs + packaging + shipping
Buffer      = subtotal * failure_rate%
Overhead    = (subtotal + buffer) * overhead%
Total Cost  = subtotal + buffer + overhead
Price       = cost_per_piece / (1 - margin%)
Gross Profit        = gross sales - item COGS
Contribution Margin = gross profit - platform fees - shipping cost
Net Profit          = not yet exposed for sales reporting until overhead allocation exists
```

## Frontend Features

- **Protected Routes** — Auto-redirect to login, preserves original URL
- **Dark/Light Theme** — Persisted to localStorage, respects system preference
- **Workspace Shell** — Role-aware workspace navigation for Control Center, Print Floor, Sell, Stock, Product Studio, Orders, Insights, and Admin while preserving legacy deep links
- **AI Insights** — Dedicated `/insights` workspace for read-only business summaries with admin-configurable `ChatGPT`, `Claude`, or `Grok` provider selection
- **Active Navigation** — Current route highlighted, admin-only items
- **Error Boundary** — Global error catch with reload action
- **Empty States** — Contextual illustrations and CTA buttons on empty lists
- **Skeleton Loaders** — Reusable loading states (table, card, stat card variants)
- **Responsive Design** — Tables on desktop, stacked cards on mobile
- **Toast Notifications** — Success/error feedback via sonner
- **Form Validation** — Inline error messages on all forms
- **Auth State** — Zustand store with auto-restore from token
- **API Rate Limiting** — 429 handling with user-friendly error messages

### Pages

- **Control Center** — Role-aware landing workspace with urgent printer, stock, sales, finance, and draft-job priorities plus quick actions into the main operational areas
- **Live Camera Feeds** — go2rtc-powered live video on printer wall cards and detail pages, MSE/WebSocket primary with MJPEG snapshot fallback, dedicated kiosk monitor page at `/print-floor/monitor/:id`
- **Print Floor** — Dedicated printer wall with grouped machine states, queue-pressure and utilization signals, reduced-chrome wall mode via `/print-floor?mode=wall`, console-style printer detail pages for live monitoring, and a defined camera-tile integration path for issue `#129`
- **Stock** — Exceptions-first inventory workspace at `/stock` with product-impacting low-stock triage, quick reconcile/adjust actions, material signals separated from finished-goods alerts, and the full ledger preserved as a secondary surface
- **Orders** — Unified queue workspace at `/orders` that stitches production jobs, fulfillment-relevant sales, printer readiness, and customer load into one operational surface while preserving the existing jobs and sales detail flows
- **Dashboard** — Classic metrics view with summary cards + 3 charts (revenue line, material pie, profit bar) + low-stock alerts + sales metrics (orders, gross sales, item COGS, gross profit, contribution margin) + revenue by channel chart
- **Insights** — Separate AI analysis workspace with focused questions, provider status, recommendations, risks, follow-up prompts, and source-of-truth evidence metrics
- **Jobs** — List with search, status filter, pagination; detail with cost breakdown; create/edit with live cost preview, now reachable inside the Orders workspace at `/orders/jobs`
- **Materials** — Full CRUD with modal, cost-per-gram preview, active/inactive toggle, mobile card layout
- **Rates** — Full CRUD with modal, unit dropdown, active/inactive toggle, mobile card layout
- **Customers** — Full CRUD with modal, search, delete, job count
- **Product Studio** — Catalog workspace at `/product-studio` with product search, readiness signals, archive/restore controls, and direct navigation into the full-page product editor
- **Product Editor** — Full-page create/edit workflow at `/product-studio/products/new` and `/product-studio/products/:id/edit` with identity, SKU/UPC, pricing, material selection, reorder policy, margin preview, readiness context, and recent stock activity
- **Product Detail** — Existing record-style detail page remains available during migration, with inventory history and stock adjustment actions plus a link into the new editor
- **Sales Inbox** — `Sell` workspace queue for recent sales with search, status/channel/payment-method filters, pagination, detail drill-in, payment method visibility, and refund/status follow-up
- **Shipping Labels** — Sales support browser-printable 4x6 shipping labels generated by the backend and printed through the local workstation browser, with explicit generated/printed metadata and reprint tracking
- **POS** — Dedicated `Sell` workspace register at `/sell` and `/sell/pos` with a split cashier layout, keyboard-wedge barcode scanning by product UPC, touch-friendly cart/payment controls, explicit guest/existing/new customer modes, and faster success/error recovery
- **New Sale** — Sale creation form with customer autocomplete, channel select, product-linked line items, shipment-label fields, shipping/tax, live total
- **Sales Channels** — CRUD for sales platforms (Etsy, Amazon, etc.) with platform fee and fixed fee configuration
- **Reports** — Tab-based sub-navigation (Inventory, Sales, P&L) with shared date range/period controls and CSV export
  - **Inventory Report** — Stock levels table with valuation, low-stock highlighting, turnover rate chart, material usage pie chart
  - **Sales Report** — Gross sales/gross profit trend chart, top products ranking, channel breakdown with fees and contribution margin
  - **Profit & Loss** — Sales-realized revenue P&L with production estimates shown separately for operational context, cost breakdown by category, stacked bar trend chart, period detail table
- **Calculator** — Standalone cost calculator with live preview and "Save as Job"
- **Admin Settings** — Editable business settings with bulk save, grouped by category, plus AI provider, model, and API-key configuration for Insights
- **Admin Users** — User management with create, edit, role assignment, deactivate/reactivate
- **Admin Data** — CSV export for jobs, materials, rates, customers, settings
- **Login** — JWT authentication with Zod validation

## Design Briefs

- [Camera Setup Guide](docs/camera-setup.md) — go2rtc configuration, Wyze camera setup, stream formats, kiosk mode, troubleshooting
- [Shipping Label Printing](docs/shipping_label_printing.md) — remote-compatible 4x6 shipping-label workflow, backend contract, workstation print path, and operator rules for print/cancel/reprint
- [AI Insights Guide](docs/ai_insights.md) — provider configuration, safety boundaries, endpoints, and UX rationale for issue `#112`
- [Role-Based Frontend Redesign User Story](docs/frontend_role_based_redesign_user_story.md) — issue-ready redesign brief for print monitoring, live views, POS, inventory, product studio, and role-based workspaces.

## Testing

### Backend test environment

- Use **Python 3.13** for local backend development and test execution.
- A repo-level `.python-version` file is included to make the expected interpreter explicit.
- Backend tests run with `TESTING=true`, which disables request rate limiting middleware so the suite does not fail with unrelated `429 Too Many Requests` responses.
- GitHub Actions CI mirrors the repo baseline with `python -m pytest backend/tests -q`, `cd frontend && npm test`, and `cd frontend && npm run build`.

```bash
# Run all backend tests
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m pytest backend/tests/ -v

# Test categories:
#   test_cost_calculator.py   - Cost calculation engine (6 tests)
#   test_api_auth.py          - Auth, RBAC, user management (18 tests)
#   test_api_settings.py      - Settings CRUD + admin guard (8 tests)
#   test_api_insights.py      - AI provider status + read-only insight flow (3 tests)
#   test_api_materials.py     - Materials CRUD + auth guard (9 tests)
#   test_api_rates.py         - Rates CRUD + auth guard (6 tests)
#   test_api_customers.py     - Customers CRUD + auth guard (8 tests)
#   test_api_jobs.py          - Jobs CRUD + auth guard + filtering (11 tests)
#   test_api_products.py       - Products CRUD + SKU generation (9 tests)
#   test_api_inventory.py      - Inventory transactions + alerts + auto-stock (7 tests)
#   test_api_sales.py          - Sales + channels CRUD, refunds, inventory, metrics (16 tests)
#   test_api_reports.py        - Inventory, sales, P&L reports + CSV + filtering (11 tests)
#   test_api_dashboard.py     - Dashboard aggregation + date filtering (6 tests)
```

## Development

### Frontend build validation

```bash
cd frontend
npm install
npm run build
npm test
```

Notes:
- TypeScript path aliasing for `@/*` is configured in both `vite.config.ts` and `tsconfig.app.json`.
- `npm run build` is the expected baseline validation step for frontend changes.
- `npm test` runs the Vitest frontend suite, including POS cashier workflow coverage.
- Frontend routes are lazy-loaded and chart-heavy dependencies are split into separate build chunks to keep the initial bundle healthier.
- `frontend/package.json` may use `overrides` to pin patched transitive dependencies when upstream toolchain ranges lag behind published security fixes.
- Barcode scanning for POS is documented in [docs/pos_barcode_scanning.md](docs/pos_barcode_scanning.md).

```bash
# Rebuild after dependency changes
docker compose build

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop services
docker compose down

# Reset database (destroys data)
docker compose down -v
docker compose up -d
```

## CI

Baseline repository CI now lives in [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).

## Deployment Docs

- [Fresh Start Guide](docs/getting_started.md)
- [web01 Compose Deployment](docs/deployment_web01_compose.md)
- [web01 Environment and Storage](docs/deployment_web01_env_and_storage.md)
- [web01 Runbook](docs/deployment_web01_runbook.md)
- [Docker Image Publishing](docs/docker_image_publish.md)

It runs on pull requests and pushes to `main` with separate jobs for:
- backend tests via `python -m pytest backend/tests -q`
- frontend tests via `cd frontend && npm test`
- frontend build validation via `cd frontend && npm run build`

Keep local validation aligned with those commands before opening or updating a PR.

## Container Publishing

The repository also includes a Docker publish workflow in [`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml).

It builds production backend and frontend images on pull requests and publishes them to Docker Hub only from approved refs:
- `main` publishes rolling `main` plus immutable `sha-*` tags
- release tags such as `v1.2.3` publish release tags plus `latest`

Required GitHub configuration:
- repository secret `DOCKERHUB_USERNAME`
- repository secret `DOCKERHUB_TOKEN`
- repository variable `DOCKERHUB_NAMESPACE`

See [docs/docker_image_publish.md](./docs/docker_image_publish.md) for the full naming, tagging, and promotion model.

## Environment Variables

See `.env.example` for all configuration options. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `SECRET_KEY` | `generate-a-random-...` | JWT signing key |
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `ADMIN_EMAIL` | `admin@example.com` | Seed admin email |
| `ADMIN_PASSWORD` | `change-me-...` | Seed admin password |
| `RATE_LIMIT_PER_MINUTE` | `120` | API rate limit per IP |
| `RATE_LIMIT_BURST` | `30` | Rate limit burst capacity |

Generate distinct local development secrets for database and auth settings before using the app. Placeholder values in tracked files are intentionally unusable, and the backend will exit until `DATABASE_URL` or `DB_PASSWORD`, `SECRET_KEY`, and `ADMIN_PASSWORD` are replaced with real values.

## Secret Scanning

The repository includes a GitHub Actions secret scan in [`.github/workflows/secret-scan.yml`](./.github/workflows/secret-scan.yml) using `gitleaks`.

Run the same check locally before publishing or opening large refactors:

```bash
gitleaks git --redact --verbose --no-banner
```

## Finance Metric Naming

See [docs/finance_metric_naming.md](./docs/finance_metric_naming.md) for the canonical glossary, naming matrix, formulas, and operational-vs-financial metric definitions used by the app.

## Expense / AP Groundwork

Phase 14 expense/AP groundwork now includes:
- [docs/vendors_and_expense_categories.md](./docs/vendors_and_expense_categories.md)
- [docs/bills_and_expenses.md](./docs/bills_and_expenses.md)
- [docs/recurring_expenses_and_reporting.md](./docs/recurring_expenses_and_reporting.md)

## Quote / A/R Groundwork

Phase 15 quote-to-cash groundwork now includes:
- [docs/quotes_workflow.md](./docs/quotes_workflow.md)
- [docs/invoice_lifecycle.md](./docs/invoice_lifecycle.md)
- [docs/ar_payments_and_aging.md](./docs/ar_payments_and_aging.md)

## Tax / Marketplace Groundwork

Phase 16 groundwork now includes:
- [docs/sales_tax_liability.md](./docs/sales_tax_liability.md)
- [docs/marketplace_settlements.md](./docs/marketplace_settlements.md)

## Finance Reporting Groundwork

Phase 17 groundwork now includes:
- [docs/finance_specialized_reports.md](./docs/finance_specialized_reports.md)
- [docs/formal_financial_statements.md](./docs/formal_financial_statements.md)
- [docs/finance_dashboard_widgets.md](./docs/finance_dashboard_widgets.md)

## Controls / Audit Groundwork

Phase 18 groundwork now includes:
- [docs/finance_audit_log.md](./docs/finance_audit_log.md)
- [docs/refund_and_adjustment_approvals.md](./docs/refund_and_adjustment_approvals.md)

## Inventory Valuation Groundwork

Phase 13 inventory accounting groundwork now includes:
- raw-material receipt / lot tracking and landed cost documentation in [docs/material_receipts_valuation.md](./docs/material_receipts_valuation.md)
- production and sales posting behavior documentation in [docs/inventory_accounting_postings.md](./docs/inventory_accounting_postings.md)
- scrap / waste / failed-print workflow documentation in [docs/scrap_and_waste_workflows.md](./docs/scrap_and_waste_workflows.md)

## Accounting Foundation Status

Phase 12 groundwork now includes initial accounting-domain tables, services, and APIs for:
- `accounts`
- `accounting_periods`
- `journal_entries`
- `journal_lines`

Current accounting foundation capabilities:
- starter chart of accounts seed
- accounting period helper/validation
- balanced-journal validation in the accounting service layer
- admin-only APIs to create/update/list accounts and periods, plus create/list/detail journal entries
- initial Alembic revision scaffolding for the accounting foundation tables
- starter chart-of-accounts usage documentation in [docs/starter_chart_of_accounts.md](./docs/starter_chart_of_accounts.md)

## Deployment Planning

Deployment planning for hosting this app on `web01.bengtson.local` via Docker is tracked in:
- [docs/deployment_web01_plan.md](./docs/deployment_web01_plan.md)
- [docs/deployment_web01_audit.md](./docs/deployment_web01_audit.md)
- [docs/deployment_web01_compose.md](./docs/deployment_web01_compose.md)
- [docs/deployment_web01_env_and_storage.md](./docs/deployment_web01_env_and_storage.md)
- [docs/deployment_web01_ingress.md](./docs/deployment_web01_ingress.md)
- [docs/deployment_web01_runbook.md](./docs/deployment_web01_runbook.md)
- GitHub issues #48–#54

## P&L Reporting Basis

The Profit & Loss report now treats:
- **sales** as realized revenue
- **jobs/production** as operational production estimates and cost accumulation

To avoid double counting, job-side `total_revenue` is shown only as an **operational production estimate** and is excluded from `total_revenue` in the P&L summary.

## Implementation Status

See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the full roadmap.

- [x] **Phase 1** — Project scaffolding, database, Docker, seed data
- [x] **Phase 2** — Core backend API: schemas, validation, OpenAPI docs, filtering, 52 tests
- [x] **Phase 3** — RBAC, user management, auth guards on mutations, 71 tests
- [x] **Phase 4** — Protected routes, theme persistence, Zod login, toasts, nav polish
- [x] **Phase 5** — All pages: dashboard charts, job CRUD with live preview, materials/rates/customers CRUD, calculator
- [x] **Phase 6** — Admin section: sidebar layout, editable settings, user management, CSV export
- [x] **Phase 7** — Polish: skeleton loaders, empty states, error boundary, responsive tables, form validation, rate limiting, production Docker
- [x] **Phase 8** — Inventory: product catalog with SKU/UPC, stock tracking, transaction ledger, auto-stock from jobs, low-stock alerts, 87 tests
- [x] **Phase 9** — Sales tracking: sales channels, orders with line items, platform fee computation, inventory deduction, refund flow, sales metrics, 103 tests
- [x] **Phase 10** — Reports: inventory/sales/P&L reports with date range filtering, period grouping, CSV export, charts, 114 tests
