from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.seed import run_seed

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "Login and user profile endpoints.",
    },
    {
        "name": "Settings",
        "description": "Business configuration: currency, margins, fees, electricity costs, and more.",
    },
    {
        "name": "Materials",
        "description": "Filament material inventory (PLA, PETG, TPU, etc.) with cost-per-gram calculation.",
    },
    {
        "name": "Rates",
        "description": "Business rates for labor, machine wear, and overhead percentages.",
    },
    {
        "name": "Customers",
        "description": "Customer records linked to print jobs for order tracking.",
    },
    {
        "name": "Jobs",
        "description": "Print jobs with automatic cost calculation, pricing, and profit analysis.",
    },
    {
        "name": "Dashboard",
        "description": "Aggregated business metrics and chart data for the admin dashboard.",
    },
    {
        "name": "Health",
        "description": "Application health check.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_seed()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "REST API for managing a 3D printing business. Tracks materials, rates, "
        "customers, and print jobs with automatic cost calculation and profit analysis. "
        "All costs are computed server-side using configurable business settings."
    ),
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
