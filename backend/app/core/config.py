from urllib.parse import quote

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "3D Print Sales API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    TESTING: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://printuser:replace-with-local-db-password@db:5432/printsales"
    DB_USER: str = "printuser"
    DB_PASSWORD: str = "replace-with-local-db-password"
    DB_NAME: str = "printsales"
    DB_HOST: str = "db"
    DB_PORT: int = 5432

    AUTO_CREATE_SCHEMA: bool = True

    SECRET_KEY: str = "replace-with-local-dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "replace-with-local-admin-password"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_BURST: int = 30

    model_config = {"env_file": ".env", "case_sensitive": True}

    def model_post_init(self, __context) -> None:
        placeholder_markers = (
            "replace-with-local-db-password",
            "replace-with-strong-db-password",
        )
        if (
            not self.DATABASE_URL
            or any(marker in self.DATABASE_URL for marker in placeholder_markers)
        ):
            encoded_password = quote(self.DB_PASSWORD, safe="")
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )

        if self.ENVIRONMENT == "production" and not self.TESTING:
            self.AUTO_CREATE_SCHEMA = False


settings = Settings()
