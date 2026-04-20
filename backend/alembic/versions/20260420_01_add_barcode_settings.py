"""add barcode / label settings

Revision ID: 20260420_01
Revises: 20260413_02
Create Date: 2026-04-20 08:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa

from app.services.settings_defaults import LABEL_SETTINGS_DATA


revision = "20260420_01"
down_revision = "20260413_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for key, value, notes in LABEL_SETTINGS_DATA:
        op.execute(
            sa.text(
                """
                INSERT INTO settings (id, key, value, notes, updated_at)
                VALUES (:id, :key, :value, :notes, NOW())
                ON CONFLICT (key) DO NOTHING
                """
            ).bindparams(
                id=uuid.uuid4(),
                key=key,
                value=value,
                notes=notes,
            )
        )


def downgrade() -> None:
    keys = [key for key, _, _ in LABEL_SETTINGS_DATA]
    op.execute(
        sa.text("DELETE FROM settings WHERE key IN :keys").bindparams(
            sa.bindparam("keys", expanding=True)
        ),
        {"keys": keys},
    )
