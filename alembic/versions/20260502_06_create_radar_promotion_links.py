"""Create Radar promotion links.

Revision ID: 20260502_06
Revises: 20260502_05
Create Date: 2026-05-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260502_06"
down_revision: str | None = "20260502_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "radar_candidate_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column(
            "radar_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("radar_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("target_slug", sa.Text(), nullable=True),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "target_type IN ('vertical_candidate', 'project', 'idea', 'task', 'decision')",
            name="radar_candidate_links_target_type_check",
        ),
        sa.CheckConstraint(
            "relation_type IN ('promoted_to', 'linked_to', 'absorbed_into', 'spawned_project')",
            name="radar_candidate_links_relation_type_check",
        ),
        sa.UniqueConstraint(
            "radar_candidate_id",
            "target_type",
            "target_id",
            "relation_type",
            name="radar_candidate_links_unique_relation",
        ),
    )
    op.create_index("radar_candidate_links_candidate_idx", "radar_candidate_links", ["radar_candidate_id"])
    op.create_index("radar_candidate_links_target_idx", "radar_candidate_links", ["target_type", "target_id"])

    op.create_table(
        "radar_promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column(
            "radar_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("radar_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'previewed'")),
        sa.Column("target_type", sa.String(length=64), nullable=False, server_default=sa.text("'vertical_candidate'")),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("payload_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('previewed', 'promoted', 'failed', 'cancelled')",
            name="radar_promotions_status_check",
        ),
        sa.CheckConstraint(
            "target_type IN ('vertical_candidate')",
            name="radar_promotions_target_type_check",
        ),
    )
    op.create_index("radar_promotions_candidate_idx", "radar_promotions", ["radar_candidate_id", "created_at"])


def downgrade() -> None:
    op.drop_index("radar_promotions_candidate_idx", table_name="radar_promotions")
    op.drop_table("radar_promotions")
    op.drop_index("radar_candidate_links_target_idx", table_name="radar_candidate_links")
    op.drop_index("radar_candidate_links_candidate_idx", table_name="radar_candidate_links")
    op.drop_table("radar_candidate_links")
