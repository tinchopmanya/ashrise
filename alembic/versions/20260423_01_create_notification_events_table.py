"""create notification events table

Revision ID: 20260423_01
Revises: 20260422_01
Create Date: 2026-04-23 13:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260423_01"
down_revision = "20260422_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("idea_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("message_type", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('telegram', 'whatsapp', 'email', 'system')",
            name="notification_events_channel_check",
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound', 'system')",
            name="notification_events_direction_check",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'failed', 'read', 'received')",
            name="notification_events_delivery_status_check",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["candidate_id"], ["vertical_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["idea_id"], ["ideas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_events_created_at", "notification_events", ["created_at"], unique=False)
    op.create_index("ix_notification_events_channel_direction", "notification_events", ["channel", "direction"], unique=False)
    op.create_index("ix_notification_events_delivery_status", "notification_events", ["delivery_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_events_delivery_status", table_name="notification_events")
    op.drop_index("ix_notification_events_channel_direction", table_name="notification_events")
    op.drop_index("ix_notification_events_created_at", table_name="notification_events")
    op.drop_table("notification_events")
