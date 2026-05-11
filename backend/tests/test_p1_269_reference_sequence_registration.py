"""#269 P1: ensure ReferenceSequence is registered with Base.metadata at startup.

Regression: `next_number` is imported lazily inside request-time functions, so
unless `app.models` (or `ReferenceSequence` directly) is imported during
application startup, the `reference_sequences` table is missing from
`Base.metadata` and the lifespan `Base.metadata.create_all` (with
`AUTO_CREATE_SCHEMA=True`) creates a fresh DB without it. The first
sale/invoice/quote auto-number allocation then fails with a missing-table
error.

The fix: `app.main` imports `app.models` explicitly so the registration is
deterministic and not dependent on transitive imports through the router.
"""

from __future__ import annotations


def test_app_main_registers_reference_sequences_table() -> None:
    import app.main  # noqa: F401
    from app.core.database import Base

    assert "reference_sequences" in Base.metadata.tables


def test_app_models_package_registers_reference_sequences_table() -> None:
    import app.models  # noqa: F401
    from app.core.database import Base

    assert "reference_sequences" in Base.metadata.tables
