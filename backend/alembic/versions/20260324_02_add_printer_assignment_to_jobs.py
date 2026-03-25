from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260324_02"
down_revision: Union[str, None] = "20260324_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("printer_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_jobs_printer_id_printers", "jobs", "printers", ["printer_id"], ["id"])
    op.create_index(op.f("ix_jobs_printer_id"), "jobs", ["printer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_printer_id"), table_name="jobs")
    op.drop_constraint("fk_jobs_printer_id_printers", "jobs", type_="foreignkey")
    op.drop_column("jobs", "printer_id")
