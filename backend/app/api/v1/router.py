from fastapi import APIRouter

from app.api.v1.endpoints import auth, customers, dashboard, inventory, jobs, materials, products, rates, reports, sales, sales_channels, settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(settings.router)
api_router.include_router(materials.router)
api_router.include_router(rates.router)
api_router.include_router(customers.router)
api_router.include_router(jobs.router)
api_router.include_router(products.router)
api_router.include_router(inventory.router)
api_router.include_router(sales_channels.router)
api_router.include_router(sales.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
