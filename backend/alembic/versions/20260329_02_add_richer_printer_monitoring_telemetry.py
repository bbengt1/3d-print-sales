"""add richer printer monitoring telemetry

Revision ID: 20260329_02
Revises: 20260329_01
Create Date: 2026-03-29 11:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_02"
down_revision = "20260329_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("printers", sa.Column("monitor_bed_target_c", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("monitor_tool_target_c", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("monitor_current_layer", sa.Integer(), nullable=True))
    op.add_column("printers", sa.Column("monitor_total_layers", sa.Integer(), nullable=True))
    op.add_column("printers", sa.Column("monitor_elapsed_seconds", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("monitor_remaining_seconds", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("monitor_eta_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("printers", sa.Column("monitor_last_event_type", sa.String(length=80), nullable=True))
    op.add_column("printers", sa.Column("monitor_last_event_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("printers", sa.Column("monitor_ws_connected", sa.Boolean(), nullable=True))
    op.add_column("printers", sa.Column("monitor_ws_last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("printers", "monitor_ws_last_error")
    op.drop_column("printers", "monitor_ws_connected")
    op.drop_column("printers", "monitor_last_event_at")
    op.drop_column("printers", "monitor_last_event_type")
    op.drop_column("printers", "monitor_eta_at")
    op.drop_column("printers", "monitor_remaining_seconds")
    op.drop_column("printers", "monitor_elapsed_seconds")
    op.drop_column("printers", "monitor_total_layers")
    op.drop_column("printers", "monitor_current_layer")
    op.drop_column("printers", "monitor_tool_target_c")
    op.drop_column("printers", "monitor_bed_target_c")
