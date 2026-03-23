from __future__ import annotations

from app.core.config import Settings


def test_settings_builds_database_url_from_db_parts_when_placeholder_present():
    settings = Settings(
        ENVIRONMENT="production",
        TESTING=False,
        DATABASE_URL="postgresql+asyncpg://printuser:replace-with-strong-db-password@db:5432/printsales",
        DB_USER="printuser",
        DB_PASSWORD="p@ss/with+symbols=ok",
        DB_NAME="printsales",
        DB_HOST="db",
        DB_PORT=5432,
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://printuser:p%40ss%2Fwith%2Bsymbols%3Dok@db:5432/printsales"
    assert settings.AUTO_CREATE_SCHEMA is False


def test_settings_preserves_explicit_database_url_outside_placeholder_case():
    settings = Settings(
        ENVIRONMENT="development",
        TESTING=False,
        DATABASE_URL="postgresql+asyncpg://custom:secret@db:5432/customdb",
        DB_USER="printuser",
        DB_PASSWORD="ignored",
        DB_NAME="printsales",
        DB_HOST="db",
        DB_PORT=5432,
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://custom:secret@db:5432/customdb"
    assert settings.AUTO_CREATE_SCHEMA is True
