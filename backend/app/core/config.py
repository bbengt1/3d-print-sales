from urllib.parse import quote

from pydantic_settings import BaseSettings


PLACEHOLDER_MARKERS = (
    "replace-with",
    "change-me",
    "generate-a-random",
    "generate-a-long-random",
)


def _contains_placeholder(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    PROJECT_NAME: str = "3D Print Sales API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    TESTING: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://printuser:change-me-local-db-password@db:5432/printsales"
    DB_USER: str = "printuser"
    DB_PASSWORD: str = "change-me-local-db-password"
    DB_NAME: str = "printsales"
    DB_HOST: str = "db"
    DB_PORT: int = 5432

    AUTO_CREATE_SCHEMA: bool = True

    SECRET_KEY: str = "generate-a-random-local-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "change-me-local-admin-password"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_BURST: int = 30

    model_config = {"env_file": ".env", "case_sensitive": True}

    def _require_real_value(self, field_name: str, value: str) -> None:
        if _contains_placeholder(value):
            raise ValueError(
                f"{field_name} still contains a tracked placeholder value. "
                "Replace it with a real secret before starting the app."
            )

    def model_post_init(self, __context) -> None:
        if (
            not self.DATABASE_URL
            or _contains_placeholder(self.DATABASE_URL)
        ):
            encoded_password = quote(self.DB_PASSWORD, safe="")
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )

        if self.ENVIRONMENT == "production" and not self.TESTING:
            self.AUTO_CREATE_SCHEMA = False

        if not self.TESTING:
            self._require_real_value("DATABASE_URL", self.DATABASE_URL)
            self._require_real_value("SECRET_KEY", self.SECRET_KEY)
            self._require_real_value("ADMIN_PASSWORD", self.ADMIN_PASSWORD)


settings = Settings()
