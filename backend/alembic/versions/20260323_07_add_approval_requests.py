"""add approval requests

Revision ID: 20260323_07
Revises: 20260323_06
Create Date: 2026-03-23 11:05:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260323_07"
down_revision: Union[str, None] = "20260323_06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approval_requests_action_type"), "approval_requests", ["action_type"], unique=False)
    op.create_index(op.f("ix_approval_requests_approved_by_user_id"), "approval_requests", ["approved_by_user_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_entity_id"), "approval_requests", ["entity_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_entity_type"), "approval_requests", ["entity_type"], unique=False)
    op.create_index(op.f("ix_approval_requests_requested_by_user_id"), "approval_requests", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_status"), "approval_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_approval_requests_status"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_requested_by_user_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_entity_type"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_entity_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_approved_by_user_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_action_type"), table_name="approval_requests")
    op.drop_table("approval_requests")
