# 3D Print Sales - Implementation Plan

## Project Overview

Full-stack web application for managing a 3D printing business. Includes a public-facing storefront, job cost/pricing calculator, and admin dashboard. Built with a modern React frontend and a Python FastAPI backend with OpenAPI/Swagger documentation.

---

## Tech Stack

### Backend
- **Framework**: Python 3.12 + FastAPI
- **Database**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.x (async)
- **Migrations**: Alembic
- **API Docs**: OpenAPI 3.1 / Swagger UI (built into FastAPI)
- **Auth**: JWT (python-jose) + bcrypt password hashing
- **Validation**: Pydantic v2
- **Testing**: pytest + httpx (async)

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **UI Library**: shadcn/ui (Tailwind CSS + Radix primitives)
- **State Management**: TanStack Query (server state) + Zustand (client state)
- **Routing**: React Router v6
- **Charts**: Recharts
- **Forms**: React Hook Form + Zod validation
- **Icons**: Lucide React
- **Theme**: Light/Dark mode toggle, modern minimal design

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Dev Environment**: Hot-reload for both frontend and backend

---

## Database Schema

### Table: `settings`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| key | VARCHAR(100) UNIQUE | e.g. `currency`, `default_profit_margin_pct` |
| value | VARCHAR(255) | Stored as string, cast in application |
| notes | TEXT | Description of the setting |
| updated_at | TIMESTAMP | |

**Seed data (from Settings sheet):**
| Key | Default Value |
|-----|---------------|
| currency | USD |
| default_profit_margin_pct | 40 |
| platform_fee_pct | 9.5 |
| fixed_fee_per_order | 0.45 |
| sales_tax_pct | 0 |
| electricity_cost_per_kwh | 0.18 |
| printer_power_draw_watts | 120 |
| failure_rate_pct | 5 |
| packaging_cost_per_order | 1.25 |
| shipping_charged_to_customer | 0 |

### Table: `materials`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | VARCHAR(50) | e.g. PLA, PETG, TPU |
| brand | VARCHAR(100) | |
| spool_weight_g | DECIMAL(10,2) | Total spool weight in grams |
| spool_price | DECIMAL(10,2) | Purchase price per spool |
| net_usable_g | DECIMAL(10,2) | Usable grams after waste |
| cost_per_g | DECIMAL(10,6) | Computed: spool_price / net_usable_g |
| notes | TEXT | |
| active | BOOLEAN | Default true |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### Table: `rates`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | VARCHAR(100) | e.g. Labor rate, Machine rate |
| value | DECIMAL(10,2) | |
| unit | VARCHAR(20) | e.g. $/hour, % |
| notes | TEXT | |
| active | BOOLEAN | Default true |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Seed data:**
| Name | Value | Unit |
|------|-------|------|
| Labor rate | 25 | $/hour |
| Machine rate | 1.5 | $/hour |
| Overhead % | 10 | % |

### Table: `customers`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | VARCHAR(200) | |
| email | VARCHAR(200) | |
| phone | VARCHAR(50) | |
| notes | TEXT | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### Table: `jobs`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| job_number | VARCHAR(50) UNIQUE | User-facing ID (e.g. 2026.3.4.001) |
| date | DATE | |
| customer_id | UUID (FK -> customers) | Nullable |
| customer_name | VARCHAR(200) | Fallback if no customer record |
| product_name | VARCHAR(200) | |
| qty_per_plate | INTEGER | |
| num_plates | INTEGER | |
| material_id | UUID (FK -> materials) | |
| total_pieces | INTEGER | Computed: qty_per_plate * num_plates |
| material_per_plate_g | DECIMAL(10,2) | |
| print_time_per_plate_hrs | DECIMAL(10,2) | |
| labor_mins | DECIMAL(10,2) | Hands-on time |
| design_time_hrs | DECIMAL(10,2) | Nullable |
| electricity_cost | DECIMAL(10,4) | Computed |
| material_cost | DECIMAL(10,4) | Computed |
| labor_cost | DECIMAL(10,4) | Computed |
| design_cost | DECIMAL(10,4) | Computed |
| machine_cost | DECIMAL(10,4) | Computed |
| packaging_cost | DECIMAL(10,4) | From settings |
| shipping_cost | DECIMAL(10,4) | |
| failure_buffer | DECIMAL(10,4) | Computed |
| subtotal_cost | DECIMAL(10,4) | Computed |
| overhead | DECIMAL(10,4) | Computed |
| total_cost | DECIMAL(10,4) | Computed |
| cost_per_piece | DECIMAL(10,4) | Computed |
| target_margin_pct | DECIMAL(5,2) | |
| price_per_piece | DECIMAL(10,4) | Computed |
| total_revenue | DECIMAL(10,4) | Computed |
| platform_fees | DECIMAL(10,4) | Computed |
| net_profit | DECIMAL(10,4) | Computed |
| profit_per_piece | DECIMAL(10,4) | Computed |
| status | VARCHAR(20) | draft, in_progress, completed, cancelled |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### Table: `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| email | VARCHAR(200) UNIQUE | |
| hashed_password | VARCHAR(255) | |
| full_name | VARCHAR(200) | |
| role | VARCHAR(20) | admin, user |
| is_active | BOOLEAN | |
| created_at | TIMESTAMP | |

---

## Cost Calculation Engine (Backend Service)

The backend replicates the spreadsheet formulas as a reusable service:

```
electricity_cost = (printer_power_watts / 1000) * print_time_hrs * num_plates * electricity_rate
material_cost = material_per_plate_g * num_plates * material.cost_per_g
labor_cost = (labor_mins / 60) * labor_rate + design_time_hrs * labor_rate
design_cost = design_time_hrs * labor_rate
machine_cost = print_time_per_plate_hrs * num_plates * machine_rate
packaging_cost = settings.packaging_cost_per_order
failure_buffer = subtotal * (failure_rate_pct / 100)
subtotal = electricity + material + labor + design + machine + packaging + shipping
overhead = subtotal * (overhead_pct / 100)
total_cost = subtotal + overhead
cost_per_piece = total_cost / total_pieces
price_per_piece = cost_per_piece / (1 - target_margin_pct / 100)
total_revenue = price_per_piece * total_pieces
platform_fees = total_revenue * (platform_fee_pct / 100) + fixed_fee_per_order
net_profit = total_revenue - total_cost - platform_fees
profit_per_piece = net_profit / total_pieces
```

---

## API Endpoints

Base URL: `/api/v1`

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login, returns JWT |
| POST | `/auth/register` | Register new user (admin only) |
| GET | `/auth/me` | Get current user profile |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/settings` | List all settings |
| GET | `/settings/{key}` | Get single setting |
| PUT | `/settings/{key}` | Update setting value |
| PUT | `/settings/bulk` | Update multiple settings |

### Materials
| Method | Path | Description |
|--------|------|-------------|
| GET | `/materials` | List materials (filter: ?active=true) |
| GET | `/materials/{id}` | Get single material |
| POST | `/materials` | Create material |
| PUT | `/materials/{id}` | Update material |
| DELETE | `/materials/{id}` | Soft-delete (set active=false) |

### Rates
| Method | Path | Description |
|--------|------|-------------|
| GET | `/rates` | List rates (filter: ?active=true) |
| GET | `/rates/{id}` | Get single rate |
| POST | `/rates` | Create rate |
| PUT | `/rates/{id}` | Update rate |
| DELETE | `/rates/{id}` | Soft-delete |

### Customers
| Method | Path | Description |
|--------|------|-------------|
| GET | `/customers` | List customers (search, pagination) |
| GET | `/customers/{id}` | Get customer with job history |
| POST | `/customers` | Create customer |
| PUT | `/customers/{id}` | Update customer |
| DELETE | `/customers/{id}` | Soft-delete |

### Jobs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List jobs (filter, sort, pagination) |
| GET | `/jobs/{id}` | Get single job with full cost breakdown |
| POST | `/jobs` | Create job (auto-calculates costs) |
| PUT | `/jobs/{id}` | Update job (recalculates costs) |
| DELETE | `/jobs/{id}` | Soft-delete |
| POST | `/jobs/calculate` | Preview cost calculation without saving |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/summary` | Aggregated metrics (total jobs, revenue, profit, etc.) |
| GET | `/dashboard/charts/revenue` | Revenue over time data |
| GET | `/dashboard/charts/materials` | Material usage breakdown |
| GET | `/dashboard/charts/profit-margins` | Profit margin trends |

---

## Frontend Pages & Components

### Public / Shared Layout
- **Header**: Logo, navigation, theme toggle (light/dark)
- **Footer**: Business info

### Page: Dashboard (`/`)
- **Summary Cards**: Total Jobs, Total Pieces, Total Revenue, Total Costs, Net Profit, Avg Margin %
- **Charts Row**:
  - Revenue over time (line chart)
  - Material usage breakdown (pie chart)
  - Profit margin trend (bar chart)
- **Recent Jobs Table**: Last 5 jobs with quick stats
- **Top Material Badge**: Most used material

### Page: Jobs (`/jobs`)
- **Job List Table**: Sortable, filterable, paginated
  - Columns: Job #, Date, Customer, Product, Pieces, Material, Total Cost, Revenue, Profit, Status
  - Row click -> detail view
- **Filters**: Date range, material, customer, status
- **"New Job" button** -> opens job form

### Page: Job Detail (`/jobs/:id`)
- **Job Header**: Job number, date, status badge, customer
- **Product Info Card**: Product name, material, quantities
- **Cost Breakdown Card**: All cost line items in a clean table
- **Pricing Card**: Margin, price per piece, revenue, fees, profit
- **Actions**: Edit, Duplicate, Delete

### Page: New/Edit Job (`/jobs/new`, `/jobs/:id/edit`)
- **Multi-section form**:
  - Section 1 - Job Info: Job number (auto-generated), date, customer (autocomplete), product name
  - Section 2 - Print Details: Material (dropdown), qty per plate, # plates, material/plate (g), print time/plate (hrs)
  - Section 3 - Labor: Labor time (mins), design time (hrs)
  - Section 4 - Costs: Shipping cost (manual), all other costs auto-calculated
  - Section 5 - Pricing: Target margin % (slider + input), price per piece (auto or manual override)
- **Live Cost Preview Panel** (sidebar): Shows calculated costs updating in real-time as inputs change
- **Save / Save & New buttons**

### Page: Materials (`/materials`)
- **Materials Table**: Name, Brand, Spool Weight, Price, Cost/g, Active status
- **Inline editing** or modal for add/edit
- **Toggle active/inactive**

### Page: Rates (`/rates`)
- **Rates Table**: Name, Value, Unit, Active status
- **Inline editing** or modal for add/edit

### Page: Customers (`/customers`)
- **Customer List**: Name, email, phone, # of jobs
- **Customer Detail**: Contact info + job history table
- **Add/Edit modal**

### Page: Cost Calculator (`/calculator`)
- **Standalone calculator** (same form as New Job but doesn't save)
- **Instant cost/pricing breakdown** as user fills in values
- **"Save as Job" button** to persist the calculation

### Admin Section (`/admin`)
- **Admin Layout**: Sidebar navigation for admin pages
- **Settings Page** (`/admin/settings`): Edit all business settings in a clean form grouped by category
  - Business: Currency
  - Pricing: Default profit margin, platform fee, fixed fee, sales tax
  - Operations: Electricity rate, printer power draw, failure rate
  - Shipping: Packaging cost, shipping model
- **User Management** (`/admin/users`): List users, add/edit/deactivate (future)
- **Data Import/Export** (`/admin/data`): Import from CSV/Excel, export jobs to CSV (future)
- **Audit Log** (`/admin/audit`): Track changes to settings and jobs (future)

---

## UI Design Specifications

### Theme
- **Color Palette**: Neutral base (slate/zinc) with a vibrant accent (indigo/violet)
- **Dark Mode**: Full dark mode support via Tailwind `dark:` classes
- **Typography**: Inter font family
- **Border Radius**: Rounded-lg (8px) for cards, rounded-md (6px) for inputs
- **Shadows**: Subtle shadows on cards, elevation on modals

### Component Patterns
- **Cards**: White bg, subtle border, rounded-lg, padding-6
- **Tables**: Striped rows, hover highlight, sticky header
- **Forms**: Floating labels or top-aligned labels, inline validation
- **Buttons**: Primary (accent color), Secondary (outline), Destructive (red)
- **Toasts**: Success/error notifications via sonner
- **Loading**: Skeleton loaders for data fetching
- **Empty States**: Illustrations + CTA for empty lists

### Responsive
- Desktop-first but fully responsive
- Sidebar collapses to hamburger on mobile
- Tables become card layouts on small screens

---

## Project Structure

```
3d-print-sales/
├── backend/
│   ├── alembic/                  # DB migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py
│   │   │   │   │   ├── settings.py
│   │   │   │   │   ├── materials.py
│   │   │   │   │   ├── rates.py
│   │   │   │   │   ├── customers.py
│   │   │   │   │   ├── jobs.py
│   │   │   │   │   └── dashboard.py
│   │   │   │   └── router.py
│   │   │   └── deps.py           # Dependency injection
│   │   ├── core/
│   │   │   ├── config.py         # App settings (env vars)
│   │   │   ├── security.py       # JWT + password hashing
│   │   │   └── database.py       # DB session factory
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── setting.py
│   │   │   ├── material.py
│   │   │   ├── rate.py
│   │   │   ├── customer.py
│   │   │   ├── job.py
│   │   │   └── user.py
│   │   ├── schemas/              # Pydantic schemas
│   │   │   ├── setting.py
│   │   │   ├── material.py
│   │   │   ├── rate.py
│   │   │   ├── customer.py
│   │   │   ├── job.py
│   │   │   ├── dashboard.py
│   │   │   └── auth.py
│   │   ├── services/
│   │   │   ├── cost_calculator.py  # Core calculation engine
│   │   │   └── job_service.py
│   │   ├── seed.py               # Seed data from spreadsheet
│   │   └── main.py               # FastAPI app entry
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── api/                  # API client (axios/fetch)
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── ui/               # shadcn components
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Footer.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── SummaryCards.tsx
│   │   │   │   └── Charts.tsx
│   │   │   ├── jobs/
│   │   │   │   ├── JobTable.tsx
│   │   │   │   ├── JobForm.tsx
│   │   │   │   ├── JobDetail.tsx
│   │   │   │   └── CostPreview.tsx
│   │   │   ├── materials/
│   │   │   │   └── MaterialTable.tsx
│   │   │   ├── rates/
│   │   │   │   └── RateTable.tsx
│   │   │   ├── customers/
│   │   │   │   ├── CustomerList.tsx
│   │   │   │   └── CustomerDetail.tsx
│   │   │   └── calculator/
│   │   │       └── Calculator.tsx
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── JobsPage.tsx
│   │   │   ├── JobDetailPage.tsx
│   │   │   ├── JobFormPage.tsx
│   │   │   ├── MaterialsPage.tsx
│   │   │   ├── RatesPage.tsx
│   │   │   ├── CustomersPage.tsx
│   │   │   ├── CalculatorPage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   └── admin/
│   │   │       ├── SettingsPage.tsx
│   │   │       ├── UsersPage.tsx
│   │   │       └── DataPage.tsx
│   │   ├── hooks/
│   │   │   ├── useJobs.ts
│   │   │   ├── useMaterials.ts
│   │   │   ├── useSettings.ts
│   │   │   └── useAuth.ts
│   │   ├── lib/
│   │   │   ├── utils.ts
│   │   │   └── cost-calculator.ts  # Client-side calc for live preview
│   │   ├── store/
│   │   │   └── auth.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── IMPLEMENTATION_PLAN.md
└── README.md
```

---

## Implementation Phases

### Phase 1: Project Scaffolding & Database - COMPLETED
1. ~~Initialize backend with FastAPI, configure project structure~~
2. ~~Initialize frontend with Vite + React + TypeScript~~
3. ~~Set up Docker Compose (Postgres, backend, frontend)~~
4. ~~Define SQLAlchemy models and create Alembic migrations~~
5. ~~Write seed script to populate settings, materials, rates from spreadsheet data~~
6. ~~Verify database schema and seed data~~

**Phase 1 Notes:** All 6 database tables created (settings, materials, rates, customers, jobs, users). Seed data from spreadsheet loaded and verified. Docker Compose running with PostgreSQL 16, FastAPI backend, and Vite React frontend. OpenAPI 3.1 Swagger docs available at `/api/v1/docs`. All CRUD endpoints implemented for settings, materials, rates, customers, jobs, and dashboard. JWT auth with admin seed user working. Frontend scaffolded with Tailwind CSS, React Router, TanStack Query, dark/light theme toggle, and all page routes wired up. Cost calculation engine service implemented replicating all spreadsheet formulas.

### Phase 2: Core Backend API - COMPLETED
1. ~~Implement settings CRUD endpoints~~
2. ~~Implement materials CRUD endpoints~~
3. ~~Implement rates CRUD endpoints~~
4. ~~Implement customers CRUD endpoints~~
5. ~~Build cost calculation engine service~~
6. ~~Implement jobs CRUD with auto-calculation~~
7. ~~Implement `/jobs/calculate` preview endpoint~~
8. ~~Implement dashboard aggregation endpoints~~
9. ~~Add OpenAPI tags, descriptions, and examples to all endpoints~~
10. ~~Write backend tests for calculation engine and endpoints~~

**Phase 2 Notes:** Extracted all inline Pydantic schemas into dedicated schema files (`backend/app/schemas/`) with full Field validation (min/max lengths, gt/ge/le constraints, regex patterns, examples). Enhanced all endpoints with OpenAPI summary/description documentation and tag metadata. Added pagination (skip/limit) to materials and rates endpoints. Added search by name/brand to materials, search by name/email to customers. Enhanced jobs list with date range filtering (date_from/date_to), customer_id filter, product name/job number search, configurable sorting (sort_by/sort_dir), and paginated response with total count. Added date range filtering to all dashboard endpoints. Cost calculator now validates material exists and is active, checks for zero total pieces, and validates margin < 100%. Job creation checks for duplicate job numbers (409 conflict). 52 tests passing covering: cost calculator (6 tests), auth (5), settings (5), materials (8), rates (5), customers (7), jobs (10), dashboard (6).

### Phase 3: Authentication - COMPLETED
1. ~~Implement user model and password hashing~~
2. ~~Build JWT login/register endpoints~~
3. ~~Add auth middleware and role-based guards~~
4. ~~Create admin user seed~~

**Phase 3 Notes:** Added `CurrentAdmin` dependency guard for role-based access control. Admin-only endpoints: user registration, user list/get/update/deactivate, settings mutations. All other mutation endpoints (materials, rates, customers, jobs POST/PUT/DELETE) require any authenticated user. GET endpoints remain public. Added user management CRUD (register, list, get, update, deactivate) under `/auth/users`. Password change endpoint at `/auth/me/password`. Self-protection: admins cannot deactivate or demote themselves. Deactivated users are blocked at login. 71 tests passing (19 auth tests including RBAC checks).

### Phase 4: Frontend Foundation
1. Set up Tailwind CSS + shadcn/ui
2. Build layout components (Header, Sidebar, Footer)
3. Configure React Router with all routes
4. Set up API client with auth interceptor
5. Implement dark/light theme toggle
6. Build auth pages (Login) and auth state management

### Phase 5: Frontend Pages
1. Dashboard page with summary cards and charts
2. Jobs list page with table, filters, pagination
3. Job detail page with cost breakdown
4. Job create/edit form with live cost preview
5. Materials management page
6. Rates management page
7. Customers list and detail pages
8. Standalone cost calculator page

### Phase 6: Admin Section
1. Admin layout with sidebar navigation
2. Settings management page (grouped form)
3. User management page (placeholder for future)
4. Data import/export page (placeholder for future)

### Phase 7: Polish & Production Readiness
1. Loading states and skeleton loaders
2. Empty states with illustrations
3. Error handling and toast notifications
4. Responsive design pass
5. Form validation (client + server)
6. API rate limiting
7. Environment-based configuration
8. Production Docker setup

---

## Key Design Decisions

1. **Cost calculations happen server-side** for accuracy and consistency. A client-side mirror is used only for the live preview in the job form.
2. **Job numbers are user-defined** (matching the spreadsheet pattern) rather than auto-incremented, allowing flexible naming schemes.
3. **Soft deletes** for materials, rates, and jobs to preserve historical data integrity.
4. **Settings as key-value pairs** for flexibility without schema changes when adding new settings.
5. **Customer is optional on jobs** - supports both named customers and anonymous/batch orders.
6. **All monetary values use DECIMAL** types to avoid floating-point precision issues.

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/print_sales

# Auth
SECRET_KEY=<random-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# App
BACKEND_CORS_ORIGINS=http://localhost:5173
ENVIRONMENT=development

# Admin seed
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<initial-password>
```
