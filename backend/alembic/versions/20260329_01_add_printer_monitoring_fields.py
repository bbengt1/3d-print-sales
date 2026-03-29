from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_01"
down_revision: Union[str, None] = "20260324_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("printers", sa.Column("monitor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("printers", sa.Column("monitor_provider", sa.String(length=50), nullable=True))
    op.add_column("printers", sa.Column("monitor_base_url", sa.String(length=500), nullable=True))
    op.add_column("printers", sa.Column("monitor_api_key", sa.String(length=255), nullable=True))
    op.add_column("printers", sa.Column("monitor_poll_interval_seconds", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("printers", sa.Column("monitor_online", sa.Boolean(), nullable=True))
    op.add_column("printers", sa.Column("monitor_status", sa.String(length=30), nullable=True))
    op.add_column("printers", sa.Column("monitor_progress_percent", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("current_print_name", sa.String(length=255), nullable=True))
    op.add_column("printers", sa.Column("monitor_last_message", sa.Text(), nullable=True))
    op.add_column("printers", sa.Column("monitor_last_error", sa.Text(), nullable=True))
    op.add_column("printers", sa.Column("monitor_bed_temp_c", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("monitor_tool_temp_c", sa.Float(), nullable=True))
    op.add_column("printers", sa.Column("monitor_last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("printers", sa.Column("monitor_last_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_printers_monitor_enabled"), "printers", ["monitor_enabled"], unique=False)
    op.create_index(op.f("ix_printers_monitor_provider"), "printers", ["monitor_provider"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_printers_monitor_provider"), table_name="printers")
    op.drop_index(op.f("ix_printers_monitor_enabled"), table_name="printers")
    op.drop_column("printers", "monitor_last_updated_at")
    op.drop_column("printers", "monitor_last_seen_at")
    op.drop_column("printers", "monitor_tool_temp_c")
    op.drop_column("printers", "monitor_bed_temp_c")
    op.drop_column("printers", "monitor_last_error")
    op.drop_column("printers", "monitor_last_message")
    op.drop_column("printers", "current_print_name")
    op.drop_column("printers", "monitor_progress_percent")
    op.drop_column("printers", "monitor_status")
    op.drop_column("printers", "monitor_online")
    op.drop_column("printers", "monitor_poll_interval_seconds")
    op.drop_column("printers", "monitor_api_key")
    op.drop_column("printers", "monitor_base_url")
    op.drop_column("printers", "monitor_provider")
    op.drop_column("printers", "monitor_enabled")
