# 3D Print Sales

Full-stack web application for managing a 3D printing business — job costing, pricing, material tracking, and business analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16 |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| **Auth** | JWT (python-jose) + bcrypt |
| **API Docs** | OpenAPI 3.1 / Swagger UI |
| **Infrastructure** | Docker Compose, multi-stage builds, nginx (production) |

## Quick Start

```bash
# Clone and start (development)
git clone <repo-url>
cd 3d-print-sales
docker compose up -d

# Services
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# Swagger:   http://localhost:8000/api/v1/docs
# ReDoc:     http://localhost:8000/api/v1/redoc
```

### Production Deployment

```bash
# Production uses nginx on port 80 with API proxy
docker compose -f docker-compose.prod.yml up -d --build

# Access at http://localhost
```

### Default Admin Login

```
Email:    admin@example.com
Password: admin123
```

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
| **Settings** | `GET/PUT /settings`, `GET/PUT /settings/{key}`, `PUT /settings/bulk` | — |
| **Materials** | Full CRUD at `/materials` | `?active`, `?search`, pagination |
| **Rates** | Full CRUD at `/rates` | `?active`, pagination |
| **Customers** | Full CRUD at `/customers` | `?search` (name/email), pagination |
| **Jobs** | Full CRUD at `/jobs`, `POST /jobs/calculate` | `?status`, `?material_id`, `?customer_id`, `?date_from`, `?date_to`, `?search`, `?sort_by`, `?sort_dir`, pagination |
| **Products** | Full CRUD at `/products` | `?is_active`, `?material_id`, `?low_stock`, `?search`, pagination |
| **Inventory** | `GET/POST /inventory/transactions`, `GET /inventory/alerts` | `?product_id`, `?type`, pagination |
| **Sales Channels** | Full CRUD at `/sales/channels` | `?is_active` |
| **Sales** | Full CRUD at `/sales`, `GET /sales/metrics`, `POST /sales/{id}/refund` | `?status`, `?channel_id`, `?customer_id`, `?date_from`, `?date_to`, `?search`, pagination |
| **Reports** | `GET /reports/inventory`, `/reports/sales`, `/reports/pl` + CSV variants | `?date_from`, `?date_to`, `?period` (daily/weekly/monthly/yearly) |
| **Dashboard** | `GET /dashboard/summary`, `/charts/revenue`, `/charts/materials`, `/charts/profit-margins` | `?date_from`, `?date_to` |

## Database

Eleven tables (6 seeded from the original spreadsheet + 2 for inventory + 3 for sales):

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

- **Dashboard** — Summary cards + 3 charts (revenue line, material pie, profit bar) + low-stock alerts + sales metrics (orders, gross sales, item COGS, gross profit, contribution margin) + revenue by channel chart
- **Jobs** — List with search, status filter, pagination; detail with cost breakdown; create/edit with live cost preview
- **Materials** — Full CRUD with modal, cost-per-gram preview, active/inactive toggle, mobile card layout
- **Rates** — Full CRUD with modal, unit dropdown, active/inactive toggle, mobile card layout
- **Customers** — Full CRUD with modal, search, delete, job count
- **Products** — Product catalog with CRUD modal, SKU/UPC, stock tracking, reorder alerts, search, pagination
- **Product Detail** — Product info with margin, inventory value, transaction history, stock adjustment
- **Sales** — Sales list with search, status/channel filters, pagination; sale detail with line items, gross profit + contribution margin breakdown, status management, refund
- **New Sale** — Sale creation form with customer autocomplete, channel select, product-linked line items, shipping/tax, live total
- **Sales Channels** — CRUD for sales platforms (Etsy, Amazon, etc.) with platform fee and fixed fee configuration
- **Reports** — Tab-based sub-navigation (Inventory, Sales, P&L) with shared date range/period controls and CSV export
  - **Inventory Report** — Stock levels table with valuation, low-stock highlighting, turnover rate chart, material usage pie chart
  - **Sales Report** — Gross sales/gross profit trend chart, top products ranking, channel breakdown with fees and contribution margin
  - **Profit & Loss** — Sales-realized revenue P&L with production estimates shown separately for operational context, cost breakdown by category, stacked bar trend chart, period detail table
- **Calculator** — Standalone cost calculator with live preview and "Save as Job"
- **Admin Settings** — Editable business settings with bulk save, grouped by category
- **Admin Users** — User management with create, edit, role assignment, deactivate/reactivate
- **Admin Data** — CSV export for jobs, materials, rates, customers, settings
- **Login** — JWT authentication with Zod validation

## Testing

### Backend test environment

- Use **Python 3.13** for local backend development and test execution.
- A repo-level `.python-version` file is included to make the expected interpreter explicit.
- Backend tests run with `TESTING=true`, which disables request rate limiting middleware so the suite does not fail with unrelated `429 Too Many Requests` responses.

```bash
# Run all backend tests
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m pytest backend/tests/ -v

# Test categories:
#   test_cost_calculator.py   - Cost calculation engine (6 tests)
#   test_api_auth.py          - Auth, RBAC, user management (18 tests)
#   test_api_settings.py      - Settings CRUD + admin guard (7 tests)
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
```

Notes:
- TypeScript path aliasing for `@/*` is configured in both `vite.config.ts` and `tsconfig.app.json`.
- `npm run build` is the expected baseline validation step for frontend changes.

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

## Environment Variables

See `.env.example` for all configuration options. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `SECRET_KEY` | `change-me...` | JWT signing key |
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `ADMIN_EMAIL` | `admin@example.com` | Seed admin email |
| `ADMIN_PASSWORD` | `admin123` | Seed admin password |
| `RATE_LIMIT_PER_MINUTE` | `120` | API rate limit per IP |
| `RATE_LIMIT_BURST` | `30` | Rate limit burst capacity |

## Finance Metric Naming

See [docs/finance_metric_naming.md](./docs/finance_metric_naming.md) for the canonical glossary, naming matrix, formulas, and operational-vs-financial metric definitions used by the app.

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
