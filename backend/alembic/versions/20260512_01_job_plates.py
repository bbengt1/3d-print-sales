"""#399: per-plate qty + printer for multi-part prints

Introduces a `plates` child table on Job so multi-part prints can record
per-plate parts_count, material_g, print_time_hrs, and printer_id.
Adds `total_material_g` and `total_print_time_hrs` columns to `jobs` so
inventory accounting and reports read a single authoritative number
instead of computing `material_per_plate_g * num_plates`. The legacy
uniform fields become nullable but stay populated for backwards-compat
on uniform jobs.

Backfill: for every existing job, insert N identical plate rows
(N = num_plates), then populate total_material_g and total_print_time_hrs.

Revision ID: 20260512_01
Revises: 20260511_06
Create Date: 2026-05-12 10:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260512_01"
down_revision = "20260511_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("plate_number", sa.Integer(), nullable=False),
        sa.Column("printer_id", sa.UUID(), nullable=True),
        sa.Column("parts_count", sa.Integer(), nullable=False),
        sa.Column("material_g", sa.Numeric(10, 2), nullable=False),
        sa.Column("print_time_hrs", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "plate_number", name="uq_plates_job_plate_number"),
    )
    op.create_index("ix_plates_job_id", "plates", ["job_id"])
    op.create_index("ix_plates_printer_id", "plates", ["printer_id"])

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("total_material_g", sa.Numeric(10, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("total_print_time_hrs", sa.Numeric(10, 2), nullable=False, server_default="0"))

    bind = op.get_bind()

    # Backfill plates from existing uniform jobs.
    jobs = bind.execute(
        sa.text(
            "SELECT id, qty_per_plate, num_plates, material_per_plate_g, "
            "print_time_per_plate_hrs, printer_id FROM jobs"
        )
    ).fetchall()

    for row in jobs:
        job_id = row[0]
        qpp = row[1]
        npl = row[2]
        mpp = row[3]
        tpp = row[4]
        printer_id = row[5]
        if qpp is None or npl is None or mpp is None or tpp is None:
            continue
        for i in range(int(npl)):
            bind.execute(
                sa.text(
                    "INSERT INTO plates (id, job_id, plate_number, printer_id, parts_count, "
                    "material_g, print_time_hrs) VALUES "
                    "(:id, :job_id, :plate_number, :printer_id, :parts_count, :material_g, :print_time_hrs)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "job_id": str(job_id),
                    "plate_number": i + 1,
                    "printer_id": str(printer_id) if printer_id else None,
                    "parts_count": int(qpp),
                    "material_g": float(mpp),
                    "print_time_hrs": float(tpp),
                },
            )
        bind.execute(
            sa.text(
                "UPDATE jobs SET total_material_g = :tmg, total_print_time_hrs = :tph "
                "WHERE id = :id"
            ),
            {
                "tmg": float(mpp) * int(npl),
                "tph": float(tpp) * int(npl),
                "id": str(job_id),
            },
        )

    # Make uniform-input fields nullable now that plates are authoritative.
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column("qty_per_plate", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("num_plates", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("material_per_plate_g", existing_type=sa.Numeric(10, 2), nullable=True)
        batch.alter_column("print_time_per_plate_hrs", existing_type=sa.Numeric(10, 2), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column("print_time_per_plate_hrs", existing_type=sa.Numeric(10, 2), nullable=False)
        batch.alter_column("material_per_plate_g", existing_type=sa.Numeric(10, 2), nullable=False)
        batch.alter_column("num_plates", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("qty_per_plate", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("total_print_time_hrs")
        batch.drop_column("total_material_g")
    op.drop_index("ix_plates_printer_id", table_name="plates")
    op.drop_index("ix_plates_job_id", table_name="plates")
    op.drop_table("plates")
