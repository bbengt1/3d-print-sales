"""add ai insight settings

Revision ID: 20260413_02
Revises: 20260413_01
Create Date: 2026-04-13 06:25:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa

from app.services.settings_defaults import AI_SETTINGS_DATA


revision = "20260413_02"
down_revision = "20260413_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for key, value, notes in AI_SETTINGS_DATA:
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
    keys = [key for key, _, _ in AI_SETTINGS_DATA]
    op.execute(
        sa.text("DELETE FROM settings WHERE key IN :keys").bindparams(
            sa.bindparam("keys", expanding=True)
        ),
        {"keys": keys},
    )
