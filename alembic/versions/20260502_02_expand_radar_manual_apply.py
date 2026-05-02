"""expand radar manual apply

Revision ID: 20260502_02
Revises: 20260502_01
Create Date: 2026-05-02 02:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260502_02"
down_revision = "20260502_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("radar_candidates", sa.Column("decision_memo", sa.Text(), nullable=True))
    op.add_column(
        "radar_candidates",
        sa.Column(
            "next_research",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "radar_candidates",
        sa.Column(
            "kill_criteria",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("radar_candidates", sa.Column("verdict", sa.Text(), nullable=True))
    op.add_column("radar_candidates", sa.Column("priority", sa.Integer(), nullable=True))
    op.execute("ALTER TABLE radar_candidates ALTER COLUMN next_research DROP DEFAULT")
    op.execute("ALTER TABLE radar_candidates ALTER COLUMN kill_criteria DROP DEFAULT")

    op.create_table(
        "radar_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_tier", sa.Text(), nullable=True),
        sa.Column("claim", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("date_accessed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["candidate_id"], ["radar_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_evidence_candidate_created_at", "radar_evidence", ["candidate_id", "created_at"], unique=False)

    op.alter_column("radar_apply_logs", "source", new_column_name="source_type", existing_type=sa.Text())
    op.alter_column(
        "radar_apply_logs",
        "request_payload",
        new_column_name="json_payload",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
    )
    op.execute("UPDATE radar_apply_logs SET source_type = 'api' WHERE source_type = 'manual' OR source_type IS NULL")
    op.execute(
        "UPDATE radar_apply_logs SET status = CASE "
        "WHEN status = 'applied' THEN 'applied' "
        "ELSE 'failed' END"
    )
    op.drop_constraint("radar_apply_logs_status_check", "radar_apply_logs", type_="check")
    op.create_check_constraint(
        "radar_apply_logs_status_check",
        "radar_apply_logs",
        "status IN ('applied', 'failed', 'dry_run')",
    )
    op.create_check_constraint(
        "radar_apply_logs_source_type_check",
        "radar_apply_logs",
        "source_type IN ('manual_paste', 'drag_drop', 'api', 'unknown')",
    )
    op.alter_column(
        "radar_apply_logs",
        "source_type",
        existing_type=sa.Text(),
        server_default=sa.text("'unknown'"),
        existing_nullable=False,
    )
    op.alter_column(
        "radar_apply_logs",
        "status",
        existing_type=sa.Text(),
        server_default=sa.text("'failed'"),
        existing_nullable=False,
    )
    op.create_index("ix_radar_apply_logs_candidate_created_at", "radar_apply_logs", ["candidate_id", "created_at"], unique=False)
    op.create_index("ix_radar_apply_logs_status_created_at", "radar_apply_logs", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_radar_apply_logs_status_created_at", table_name="radar_apply_logs")
    op.drop_index("ix_radar_apply_logs_candidate_created_at", table_name="radar_apply_logs")
    op.alter_column(
        "radar_apply_logs",
        "status",
        existing_type=sa.Text(),
        server_default=sa.text("'received'"),
        existing_nullable=False,
    )
    op.alter_column(
        "radar_apply_logs",
        "source_type",
        existing_type=sa.Text(),
        server_default=sa.text("'manual'"),
        existing_nullable=False,
    )
    op.drop_constraint("radar_apply_logs_source_type_check", "radar_apply_logs", type_="check")
    op.drop_constraint("radar_apply_logs_status_check", "radar_apply_logs", type_="check")
    op.create_check_constraint(
        "radar_apply_logs_status_check",
        "radar_apply_logs",
        "status IN ('received', 'applied', 'rejected', 'partial')",
    )
    op.execute("UPDATE radar_apply_logs SET source_type = 'manual' WHERE source_type = 'api'")
    op.alter_column(
        "radar_apply_logs",
        "json_payload",
        new_column_name="request_payload",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
    )
    op.alter_column("radar_apply_logs", "source_type", new_column_name="source", existing_type=sa.Text())

    op.drop_index("ix_radar_evidence_candidate_created_at", table_name="radar_evidence")
    op.drop_table("radar_evidence")

    op.drop_column("radar_candidates", "priority")
    op.drop_column("radar_candidates", "verdict")
    op.drop_column("radar_candidates", "kill_criteria")
    op.drop_column("radar_candidates", "next_research")
    op.drop_column("radar_candidates", "decision_memo")
