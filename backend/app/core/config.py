from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "3D Print Sales API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production

    DATABASE_URL: str = "postgresql+asyncpg://printuser:printpass@db:5432/printsales"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "admin123"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_BURST: int = 30

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
