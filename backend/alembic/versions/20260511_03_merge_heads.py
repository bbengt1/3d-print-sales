"""Merge divergent heads 20260510_13 + 20260511_02

Two migrations were added in parallel branches both descending from
20260510_12: PR #384 (`20260510_13_backfill_je_reference_sequence`) and
the #318/#316 chain (`20260511_01_product_location_stock` →
`20260511_02_bank_rule_targets`). This merge revision joins them so
`alembic upgrade head` resolves to a single head again.

No DDL — pure topology fix.

Revision ID: 20260511_03
Revises: 20260510_13, 20260511_02
Create Date: 2026-05-11 12:30:00
"""

from __future__ import annotations


revision = "20260511_03"
down_revision = ("20260510_13", "20260511_02")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
