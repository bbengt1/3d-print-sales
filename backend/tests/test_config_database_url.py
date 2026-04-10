from __future__ import annotations

import pytest

from app.core.config import Settings


def test_settings_builds_database_url_from_db_parts_when_placeholder_present():
    settings = Settings(
        ENVIRONMENT="production",
        TESTING=False,
        DATABASE_URL="postgresql+asyncpg://printuser:change-me-production-db-password@db:5432/printsales",
        DB_USER="printuser",
        DB_PASSWORD="p@ss/with+symbols=ok",
        DB_NAME="printsales",
        DB_HOST="db",
        DB_PORT=5432,
        SECRET_KEY="a-real-production-secret-key",
        ADMIN_PASSWORD="a-real-production-admin-password",
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
        SECRET_KEY="a-real-development-secret-key",
        ADMIN_PASSWORD="a-real-development-admin-password",
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://custom:secret@db:5432/customdb"
    assert settings.AUTO_CREATE_SCHEMA is True


def test_settings_reject_placeholder_secret_key_when_not_testing():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="development",
            TESTING=False,
            DATABASE_URL="postgresql+asyncpg://custom:secret@db:5432/customdb",
            SECRET_KEY="generate-a-random-local-secret-key",
            ADMIN_PASSWORD="actually-secure-admin-password",
        )


def test_settings_reject_placeholder_admin_password_when_not_testing():
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings(
            ENVIRONMENT="development",
            TESTING=False,
            DATABASE_URL="postgresql+asyncpg://custom:secret@db:5432/customdb",
            SECRET_KEY="a-real-secret-key",
            ADMIN_PASSWORD="change-me-local-admin-password",
        )
