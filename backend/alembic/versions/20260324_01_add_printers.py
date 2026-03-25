from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260324_01"
down_revision: Union[str, None] = "20260323_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "printers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("manufacturer", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_printers_name"), "printers", ["name"], unique=False)
    op.create_index(op.f("ix_printers_slug"), "printers", ["slug"], unique=False)
    op.create_index(op.f("ix_printers_status"), "printers", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_printers_status"), table_name="printers")
    op.drop_index(op.f("ix_printers_slug"), table_name="printers")
    op.drop_index(op.f("ix_printers_name"), table_name="printers")
    op.drop_table("printers")
