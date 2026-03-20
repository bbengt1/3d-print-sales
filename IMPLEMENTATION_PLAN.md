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

### Table: `products`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| sku | VARCHAR(50) UNIQUE | Auto-generated: PRD-{MATERIAL}-{NNNN} |
| upc | VARCHAR(14) | Optional UPC/EAN barcode |
| name | VARCHAR(200) | |
| description | TEXT | |
| material_id | UUID (FK -> materials) | Primary material used |
| unit_cost | DECIMAL(10,4) | Rolling avg production cost |
| unit_price | DECIMAL(10,4) | Default selling price |
| stock_qty | INTEGER | Current stock on hand |
| reorder_point | INTEGER | Low-stock alert threshold |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### Table: `inventory_transactions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| product_id | UUID (FK -> products) | |
| job_id | UUID (FK -> jobs) | Nullable, source job if produced |
| type | VARCHAR(20) | production, sale, adjustment, return, waste |
| quantity | INTEGER | Positive = add, negative = remove |
| unit_cost | DECIMAL(10,4) | Cost at time of transaction |
| notes | TEXT | |
| created_by | UUID (FK -> users) | |
| created_at | TIMESTAMP | |

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

### Products
| Method | Path | Description |
|--------|------|-------------|
| GET | `/products` | List products (search, filter by material/stock/active, pagination) |
| GET | `/products/{id}` | Get single product |
| POST | `/products` | Create product (auto-generates SKU) |
| PUT | `/products/{id}` | Update product |
| DELETE | `/products/{id}` | Soft-delete (set is_active=false) |

### Inventory
| Method | Path | Description |
|--------|------|-------------|
| GET | `/inventory/transactions` | List transactions (filter by product, type, pagination) |
| POST | `/inventory/transactions` | Manual stock adjustment |
| GET | `/inventory/alerts` | Products & materials below reorder point |

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

### Page: Products (`/products`)
- **Product List Table**: SKU, name, price, cost, stock (with low-stock warnings), active status
- **Search** by name or SKU
- **CRUD Modal**: Add/edit products with material dropdown, price, reorder point, optional UPC
- **Active/Inactive toggle**
- **Row click** -> detail view
- **Pagination**

### Page: Product Detail (`/products/:id`)
- **Product Info Card**: SKU, UPC, name, description, price, cost, margin, stock, inventory value
- **Transaction History Table**: Date, type (color-coded badges), quantity (+/-), unit cost, notes
- **Adjust Stock Modal**: Type selector, quantity, notes

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

### Phase 4: Frontend Foundation - COMPLETED
1. ~~Set up Tailwind CSS + shadcn/ui~~
2. ~~Build layout components (Header, Sidebar, Footer)~~
3. ~~Configure React Router with all routes~~
4. ~~Set up API client with auth interceptor~~
5. ~~Implement dark/light theme toggle~~
6. ~~Build auth pages (Login) and auth state management~~

**Phase 4 Notes:** Added ProtectedRoute wrapper that auto-fetches user profile on page load if token exists, redirects to login if unauthenticated, and preserves redirect-back location. Dark/light theme now persists to localStorage and respects system preference on first visit via `useTheme` hook. Header enhanced with active nav highlighting (current route highlighted in primary color), user name display with avatar icon, admin-only nav item visibility, and mobile-responsive menu. Login page enhanced with Zod schema validation (email format, required fields), inline field error messages, loading spinner, server error display (including "Account deactivated"), redirect to original page after login, theme toggle on login page, and default credentials hint. Toast notifications (sonner) wired up globally via `<Toaster>` component with `richColors` and welcome toast on login. Auth store extended with `setUser` and `isAuthenticated()` helper. Frontend TypeScript compilation and production build verified.

### Phase 5: Frontend Pages - COMPLETED
1. ~~Dashboard page with summary cards and charts~~
2. ~~Jobs list page with table, filters, pagination~~
3. ~~Job detail page with cost breakdown~~
4. ~~Job create/edit form with live cost preview~~
5. ~~Materials management page~~
6. ~~Rates management page~~
7. ~~Customers list and detail pages~~
8. ~~Standalone cost calculator page~~

**Phase 5 Notes:** Dashboard enhanced with 3 Recharts visualizations: revenue over time (line chart), material usage (pie chart), and profit margin by job (bar chart). Jobs page enhanced with search filter, status dropdown filter, pagination with page controls, color-coded status badges, and profit coloring (green/red). Job detail page shows full cost breakdown table, pricing/profit analysis with actual margin calculation, info cards (date, customer, pieces, print time), edit/delete actions. Job form with multi-section layout (job info, print details, labor/costs), material dropdown, target margin slider, status select, client-side validation, and sticky live cost preview sidebar that updates in real-time via the `/jobs/calculate` API. Materials page with full CRUD modal (create/edit), inline cost-per-gram calculation preview, active/inactive toggle. Rates page with CRUD modal, unit dropdown. Customers page with CRUD modal, search, delete confirmation, job count display. Standalone calculator with same live preview as job form plus "Save as Job" button that pre-fills the job form.

### Phase 6: Admin Section - COMPLETED
1. ~~Admin layout with sidebar navigation~~
2. ~~Settings management page (grouped form)~~
3. ~~User management page (placeholder for future)~~
4. ~~Data import/export page (placeholder for future)~~

**Phase 6 Notes:** Built AdminLayout component with persistent sidebar navigation (Settings, Users, Data Export) and admin-only access guard (redirects non-admins to dashboard). Mobile-responsive with horizontal tab bar on small screens. Settings page converted from read-only to fully editable grouped form with bulk save via PUT /settings/bulk, dirty state tracking, and Save Changes button. User management page with full CRUD: create users with role assignment, edit name/email/role, deactivate/reactivate users, role badges (admin=purple, user=blue), "(you)" indicator for current user, self-protection (can't deactivate yourself). Data export page with CSV download for all 5 resources (jobs, materials, rates, customers, settings) with proper CSV escaping and timestamped filenames. Admin routes nested under /admin with index redirect to /admin/settings.

### Phase 7: Polish & Production Readiness - COMPLETED
1. ~~Loading states and skeleton loaders~~
2. ~~Empty states with illustrations~~
3. ~~Error handling and toast notifications~~
4. ~~Responsive design pass~~
5. ~~Form validation (client + server)~~
6. ~~API rate limiting~~
7. ~~Environment-based configuration~~
8. ~~Production Docker setup~~

**Phase 7 Notes:** Created reusable UI components: Skeleton (with SkeletonCard, SkeletonTable, SkeletonStatCards variants), EmptyState (with icon map for jobs, materials, rates, customers), and ErrorBoundary (class component with error display and reload button). ErrorBoundary wraps the entire app at the top level. Materials and Rates pages updated with proper SkeletonTable loading, EmptyState with CTA buttons, and mobile-responsive card layouts (tables on desktop, stacked cards on mobile). All form modals enhanced with inline validation and error messages. Backend rate limiter middleware added using token-bucket algorithm keyed by client IP (configurable via RATE_LIMIT_PER_MINUTE and RATE_LIMIT_BURST env vars, defaults 120/30). Config extended with ENVIRONMENT and rate limit settings. Multi-stage Docker builds: backend has development (with --reload) and production (with --workers 4 and non-root user) targets; frontend has development, build, and production (nginx:alpine with gzip, asset caching, API proxy, SPA fallback) targets. Added docker-compose.prod.yml for production deployment with env-var driven config, restart policies, and nginx on port 80. Updated .env.example with all new variables.


### Phase 8: Inventory Management - COMPLETED
1. ~~Create `products` table with auto-generated SKU (PRD-{MATERIAL}-{NNNN}), optional UPC/EAN field~~
2. ~~Create `inventory_transactions` table for stock movement ledger~~
3. ~~Extend `materials` table with spools_in_stock and reorder_point columns~~
4. ~~Extend `jobs` table with product_id FK and inventory_added flag~~
5. ~~SKU auto-generation service~~
6. ~~Inventory service: stock adjustments, production auto-add, rolling average cost~~
7. ~~Product CRUD API endpoints with search, pagination, low-stock filter~~
8. ~~Inventory transaction endpoints (list, create adjustments)~~
9. ~~Low-stock alerts endpoint (products and materials below reorder point)~~
10. ~~Auto-inventory: completed jobs with linked product auto-create production transactions~~
11. ~~Products page with CRUD modal, search, pagination, stock warnings~~
12. ~~Product detail page with transaction history and stock adjustment modal~~
13. ~~Dashboard inventory alerts widget~~
14. ~~Job form product dropdown with inventory auto-add hint~~
15. ~~Materials page spool stock column and edit fields~~
16. ~~Navigation update with Products link~~
17. ~~16 backend tests (9 product + 7 inventory)~~

**Phase 8 Notes:** Two new database tables: `products` (finished product catalog with SKU, UPC, stock tracking, pricing, reorder point) and `inventory_transactions` (stock movement ledger with types: production, sale, adjustment, return, waste). Extended `materials` with spools_in_stock and reorder_point for filament inventory tracking. Extended `jobs` with product_id FK and inventory_added boolean for auto-stock integration. SKU auto-generation follows PRD-{MATERIAL_CODE}-{NNNN} format (e.g., PRD-PLA-0001). Inventory service handles stock adjustments with rolling average unit cost calculation. When a job is created/updated to "completed" status and linked to a product, a production transaction is auto-created and product stock is incremented. Low-stock alerts endpoint returns both products and materials below their reorder points. Frontend Products page follows existing CRUD modal pattern with search, pagination, active/inactive toggle, and low-stock warning indicators. Product detail page shows full transaction history with color-coded transaction types and manual stock adjustment modal. Dashboard enhanced with low-stock alerts panel linking to affected products/materials. Job form enhanced with product dropdown and inventory auto-add hint. Materials page updated with spool stock column and edit fields.

### Phase 9: Sales Tracking
1. Create `sales_channels` table with per-channel fee configuration
2. Create `sales` table with sale_number auto-generation, status flow, payment tracking
3. Create `sale_items` table linking to products/jobs
4. Sales channel CRUD endpoints
5. Sales CRUD endpoints with auto-computation (fees, totals, net revenue)
6. Sale creation auto-deducts inventory
7. Refund flow with inventory restoration
8. Sales metrics endpoint (revenue, units, AOV, refund rate, by-channel)
9. Sales page with filters and pagination
10. Sale detail page with line items and P&L
11. New sale form with product/job line items
12. Sales channels management page
13. Dashboard sales metrics and charts
14. Customer detail purchase history
15. Backend tests (~15 tests)

### Phase 10: Reports
1. Inventory reports: stock levels with valuation, turnover rate, material usage, dead stock
2. Sales reports: revenue over time with period comparison, by product/channel/customer
3. Profit & Loss report combining all data
4. Report generation service with date range and period grouping
5. CSV export for all reports
6. Reports section with sub-navigation (Inventory, Sales, P&L)
7. Shared report controls (date picker, period toggle, export button)
8. Inventory reports page with stock table, turnover chart, material usage chart
9. Sales reports page with revenue chart, product ranking, channel breakdown
10. P&L page with summary cards and trend chart
11. Backend tests (~10 tests)

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
