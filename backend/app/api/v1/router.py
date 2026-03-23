from fastapi import APIRouter

from app.api.v1.endpoints import accounting, approvals, audit, auth, customers, dashboard, inventory, invoices, jobs, materials, products, quotes, rates, reports, sales, sales_channels, settlements, settings, tax

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(accounting.router)
api_router.include_router(approvals.router)
api_router.include_router(audit.router)
api_router.include_router(settings.router)
api_router.include_router(materials.router)
api_router.include_router(rates.router)
api_router.include_router(customers.router)
api_router.include_router(jobs.router)
api_router.include_router(products.router)
api_router.include_router(quotes.router)
api_router.include_router(invoices.router)
api_router.include_router(inventory.router)
api_router.include_router(sales_channels.router)
api_router.include_router(sales.router)
api_router.include_router(settlements.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
api_router.include_router(tax.router)
