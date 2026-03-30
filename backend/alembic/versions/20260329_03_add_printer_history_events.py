"""add printer history events

Revision ID: 20260329_03
Revises: 20260329_02
Create Date: 2026-03-29 19:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_03"
down_revision = "20260329_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "printer_history_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("printer_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_printer_history_events_actor_user_id"), "printer_history_events", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_printer_history_events_created_at"), "printer_history_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_printer_history_events_event_type"), "printer_history_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_printer_history_events_job_id"), "printer_history_events", ["job_id"], unique=False)
    op.create_index(op.f("ix_printer_history_events_printer_id"), "printer_history_events", ["printer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_printer_history_events_printer_id"), table_name="printer_history_events")
    op.drop_index(op.f("ix_printer_history_events_job_id"), table_name="printer_history_events")
    op.drop_index(op.f("ix_printer_history_events_event_type"), table_name="printer_history_events")
    op.drop_index(op.f("ix_printer_history_events_created_at"), table_name="printer_history_events")
    op.drop_index(op.f("ix_printer_history_events_actor_user_id"), table_name="printer_history_events")
    op.drop_table("printer_history_events")
