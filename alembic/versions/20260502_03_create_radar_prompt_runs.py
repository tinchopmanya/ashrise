"""create radar prompt runs

Revision ID: 20260502_03
Revises: 20260502_02
Create Date: 2026-05-02 15:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260502_03"
down_revision = "20260502_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "radar_prompt_versions",
        sa.Column("variables_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("radar_prompt_versions", sa.Column("system_notes", sa.Text(), nullable=True))

    op.create_table(
        "radar_prompt_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("prompt_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("target_tool", sa.Text(), nullable=False),
        sa.Column("model_label", sa.Text(), nullable=True),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("expected_filename", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("apply_log_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "target_tool IN ('chatgpt_web', 'claude_web', 'codex', 'other')",
            name="radar_prompt_runs_target_tool_check",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'copied', 'waiting_import', 'applied', 'cancelled', 'failed')",
            name="radar_prompt_runs_status_check",
        ),
        sa.ForeignKeyConstraint(["prompt_id"], ["radar_prompts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["radar_prompt_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["radar_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["apply_log_id"], ["radar_apply_logs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_prompt_runs_created_at", "radar_prompt_runs", ["created_at"], unique=False)
    op.create_index("ix_radar_prompt_runs_candidate_status", "radar_prompt_runs", ["candidate_id", "status"], unique=False)
    op.create_index("ix_radar_prompt_runs_prompt_status", "radar_prompt_runs", ["prompt_id", "status"], unique=False)
    op.execute(
        "CREATE TRIGGER radar_prompt_runs_touch BEFORE UPDATE ON radar_prompt_runs "
        "FOR EACH ROW EXECUTE FUNCTION touch_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS radar_prompt_runs_touch ON radar_prompt_runs;")
    op.drop_index("ix_radar_prompt_runs_prompt_status", table_name="radar_prompt_runs")
    op.drop_index("ix_radar_prompt_runs_candidate_status", table_name="radar_prompt_runs")
    op.drop_index("ix_radar_prompt_runs_created_at", table_name="radar_prompt_runs")
    op.drop_table("radar_prompt_runs")
    op.drop_column("radar_prompt_versions", "system_notes")
    op.drop_column("radar_prompt_versions", "variables_schema")
