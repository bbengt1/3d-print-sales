# 3D Print Sales

Full-stack web application for managing a 3D printing business — job costing, pricing, material tracking, and business analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16 |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| **Auth** | JWT (python-jose) + bcrypt |
| **API Docs** | OpenAPI 3.1 / Swagger UI |
| **Infrastructure** | Docker Compose |

## Quick Start

```bash
# Clone and start
git clone <repo-url>
cd 3d-print-sales
docker compose up -d

# Services
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# Swagger:   http://localhost:8000/api/v1/docs
# ReDoc:     http://localhost:8000/api/v1/redoc
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
│   │   ├── api/v1/        # REST endpoints (auth, settings, materials, rates, customers, jobs, dashboard)
│   │   ├── core/          # Config, database, security
│   │   ├── models/        # SQLAlchemy models (6 tables)
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Cost calculation engine
│   │   ├── seed.py        # Database seed data
│   │   └── main.py        # App entry point
│   ├── alembic/           # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/              # React + TypeScript application
│   ├── src/
│   │   ├── api/           # Axios API client
│   │   ├── components/    # Layout, UI components
│   │   ├── pages/         # Route pages (Dashboard, Jobs, Materials, Rates, etc.)
│   │   ├── store/         # Zustand auth store
│   │   ├── types/         # TypeScript interfaces
│   │   └── lib/           # Utilities
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── IMPLEMENTATION_PLAN.md
```

## API Endpoints

All endpoints are under `/api/v1`:

| Resource | Endpoints | Filters |
|----------|-----------|---------|
| **Auth** | `POST /auth/login`, `GET /auth/me`, `PUT /auth/me/password`, `POST /auth/register` (admin), `GET/PUT/DELETE /auth/users` (admin) | `?is_active` |
| **Settings** | `GET/PUT /settings`, `GET/PUT /settings/{key}`, `PUT /settings/bulk` | — |
| **Materials** | Full CRUD at `/materials` | `?active`, `?search`, pagination |
| **Rates** | Full CRUD at `/rates` | `?active`, pagination |
| **Customers** | Full CRUD at `/customers` | `?search` (name/email), pagination |
| **Jobs** | Full CRUD at `/jobs`, `POST /jobs/calculate` | `?status`, `?material_id`, `?customer_id`, `?date_from`, `?date_to`, `?search`, `?sort_by`, `?sort_dir`, pagination |
| **Dashboard** | `GET /dashboard/summary`, `/charts/revenue`, `/charts/materials`, `/charts/profit-margins` | `?date_from`, `?date_to` |

## Database

Six tables seeded from the original spreadsheet:

- **settings** — Business configuration (currency, margins, fees, electricity rates)
- **materials** — Filament inventory (PLA, PETG, TPU, ABS, PLA+) with cost-per-gram
- **rates** — Labor rate ($25/hr), machine rate ($1.50/hr), overhead (10%)
- **customers** — Customer contact information
- **jobs** — Full job tracking with 17 computed cost/pricing fields
- **users** — Admin authentication

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
Profit      = revenue - costs - platform_fees
```

## Frontend Pages

- **Dashboard** — Summary cards with key metrics
- **Jobs** — List, create, view, edit jobs with full cost breakdown
- **Materials** — View and manage filament inventory
- **Rates** — View and manage labor/machine/overhead rates
- **Customers** — Customer management (placeholder)
- **Calculator** — Standalone cost calculator (placeholder)
- **Admin Settings** — Business configuration grouped by category
- **Login** — JWT authentication

## Testing

```bash
# Run all backend tests (71 tests)
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v

# Test categories:
#   test_cost_calculator.py   - Cost calculation engine (6 tests)
#   test_api_auth.py          - Auth, RBAC, user management (18 tests)
#   test_api_settings.py      - Settings CRUD + admin guard (7 tests)
#   test_api_materials.py     - Materials CRUD + auth guard (9 tests)
#   test_api_rates.py         - Rates CRUD + auth guard (6 tests)
#   test_api_customers.py     - Customers CRUD + auth guard (8 tests)
#   test_api_jobs.py          - Jobs CRUD + auth guard + filtering (11 tests)
#   test_api_dashboard.py     - Dashboard aggregation + date filtering (6 tests)
```

## Development

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
| `ADMIN_EMAIL` | `admin@example.com` | Seed admin email |
| `ADMIN_PASSWORD` | `admin123` | Seed admin password |

## Implementation Status

See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the full roadmap.

- [x] **Phase 1** — Project scaffolding, database, Docker, seed data
- [x] **Phase 2** — Core backend API: schemas, validation, OpenAPI docs, filtering, 52 tests
- [x] **Phase 3** — RBAC, user management, auth guards on mutations, 71 tests
- [ ] **Phase 4** — Frontend foundation polish
- [ ] **Phase 5** — Full frontend pages (forms, detail views, calculator)
- [ ] **Phase 6** — Admin section
- [ ] **Phase 7** — Polish & production readiness
