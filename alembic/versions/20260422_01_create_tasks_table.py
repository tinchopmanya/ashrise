"""create tasks table

Revision ID: 20260422_01
Revises:
Create Date: 2026-04-22 10:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260422_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("idea_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'backlog'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("promoted_to", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(idea_id IS NOT NULL) OR (project_id IS NOT NULL) OR (candidate_id IS NOT NULL)",
            name="tasks_requires_owner",
        ),
        sa.CheckConstraint(
            "status IN ('backlog', 'ready', 'progress', 'blocked', 'done')",
            name="tasks_status_check",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["vertical_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["idea_id"], ["ideas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_idea_id", "tasks", ["idea_id"], unique=False)
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"], unique=False)
    op.create_index("ix_tasks_candidate_id", "tasks", ["candidate_id"], unique=False)
    op.create_index("ix_tasks_status_position", "tasks", ["status", "position", "updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_status_position", table_name="tasks")
    op.drop_index("ix_tasks_candidate_id", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_index("ix_tasks_idea_id", table_name="tasks")
    op.drop_table("tasks")
