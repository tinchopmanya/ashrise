"""Radar file imports watcher foundation.

Revision ID: 20260502_04
Revises: 20260502_03
Create Date: 2026-05-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260502_04"
down_revision: str | None = "20260502_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("radar_apply_logs_source_type_check", "radar_apply_logs", type_="check")
    op.create_check_constraint(
        "radar_apply_logs_source_type_check",
        "radar_apply_logs",
        "source_type IN ('manual_paste', 'drag_drop', 'api', 'file_watcher', 'unknown')",
    )

    op.drop_constraint("radar_file_imports_status_check", "radar_file_imports", type_="check")
    op.execute("UPDATE radar_file_imports SET status = 'processed' WHERE status = 'applied'")
    op.alter_column("radar_file_imports", "file_name", new_column_name="filename", existing_type=sa.Text())
    op.alter_column("radar_file_imports", "file_path", new_column_name="original_path", existing_type=sa.Text())
    op.add_column("radar_file_imports", sa.Column("stored_path", sa.Text(), nullable=True))
    op.execute("UPDATE radar_file_imports SET file_hash = id::text WHERE file_hash IS NULL")
    op.alter_column("radar_file_imports", "file_hash", existing_type=sa.Text(), nullable=False)
    op.drop_column("radar_file_imports", "source_kind")
    op.create_check_constraint(
        "radar_file_imports_status_check",
        "radar_file_imports",
        "status IN ('pending', 'processed', 'failed', 'duplicate')",
    )
    op.create_index("ix_radar_file_imports_hash", "radar_file_imports", ["file_hash"], unique=False)
    op.create_index("ix_radar_file_imports_status_created_at", "radar_file_imports", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_radar_file_imports_status_created_at", table_name="radar_file_imports")
    op.drop_index("ix_radar_file_imports_hash", table_name="radar_file_imports")
    op.drop_constraint("radar_file_imports_status_check", "radar_file_imports", type_="check")
    op.add_column(
        "radar_file_imports",
        sa.Column("source_kind", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
    )
    op.alter_column("radar_file_imports", "file_hash", existing_type=sa.Text(), nullable=True)
    op.drop_column("radar_file_imports", "stored_path")
    op.alter_column("radar_file_imports", "original_path", new_column_name="file_path", existing_type=sa.Text())
    op.alter_column("radar_file_imports", "filename", new_column_name="file_name", existing_type=sa.Text())
    op.execute("UPDATE radar_file_imports SET status = 'applied' WHERE status = 'processed'")
    op.create_check_constraint(
        "radar_file_imports_status_check",
        "radar_file_imports",
        "status IN ('pending', 'applied', 'failed', 'duplicate')",
    )

    op.drop_constraint("radar_apply_logs_source_type_check", "radar_apply_logs", type_="check")
    op.execute("UPDATE radar_apply_logs SET source_type = 'unknown' WHERE source_type = 'file_watcher'")
    op.create_check_constraint(
        "radar_apply_logs_source_type_check",
        "radar_apply_logs",
        "source_type IN ('manual_paste', 'drag_drop', 'api', 'unknown')",
    )
