"""create radar foundation

Revision ID: 20260502_01
Revises: 20260423_01
Create Date: 2026-05-02 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260502_01"
down_revision = "20260423_01"
branch_labels = None
depends_on = None


RADAR_TAXONOMIES = {
    "focus": [
        "quick_win",
        "mediano_plazo",
        "moonshot",
        "unicorn_potential",
        "defensive_tool",
        "cashflow_service",
        "research_bet",
        "infra_layer",
    ],
    "scope": [
        "uruguay",
        "latam",
        "global",
        "uruguay_first_latam_later",
        "global_from_day_one",
    ],
    "maturity": [
        "raw_signal",
        "candidate",
        "researched",
        "validated_problem",
        "validated_buyer",
        "prototype_ready",
        "pilot_ready",
        "commercialized",
        "killed",
        "absorbed",
    ],
    "build_level": [
        "standalone_product",
        "module",
        "feature",
        "internal_tool",
        "data_pipeline",
        "agent_workflow",
        "service_offer",
    ],
    "time_horizon": [
        "0_30_days",
        "30_90_days",
        "3_12_months",
        "12_36_months",
    ],
    "expected_return": [
        "cashflow",
        "strategic_learning",
        "data_asset",
        "platform_capability",
        "brand_signal",
        "enterprise_contract",
        "licensable_ip",
    ],
    "dominant_risk": [
        "market_risk",
        "technical_risk",
        "data_risk",
        "regulatory_risk",
        "sales_risk",
        "execution_risk",
        "commoditization_risk",
        "capital_risk",
    ],
    "validation_mode": [
        "interviews",
        "fake_door",
        "manual_concierge",
        "paid_pilot",
        "data_probe",
        "prototype_demo",
        "landing_page",
        "outreach_campaign",
    ],
    "evidence_requirement": [
        "low",
        "medium",
        "high",
        "strict",
    ],
    "buyer_type": [
        "sme_owner",
        "enterprise_ops",
        "public_sector",
        "software_factory",
        "consultant",
        "regulated_industry",
        "consumer",
        "developer",
        "investor",
    ],
    "preferred_channel": [
        "direct_sales",
        "linkedin_outreach",
        "industry_association",
        "partner_channel",
        "marketplace",
        "content",
        "open_source_distribution",
        "government_procurement",
        "consulting_entry",
    ],
    "initial_strategy": [
        "sell_first",
        "build_first",
        "research_first",
        "consulting_first",
        "data_first",
        "open_source_first",
        "partner_first",
        "clone_and_localize",
    ],
}


def upgrade() -> None:
    op.create_table(
        "radar_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("focus", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("maturity", sa.Text(), nullable=True, server_default=sa.text("'candidate'")),
        sa.Column("build_level", sa.Text(), nullable=True),
        sa.Column("time_horizon", sa.Text(), nullable=True),
        sa.Column("expected_return", sa.Text(), nullable=True),
        sa.Column("dominant_risk", sa.Text(), nullable=True),
        sa.Column("validation_mode", sa.Text(), nullable=True),
        sa.Column("evidence_requirement", sa.Text(), nullable=True),
        sa.Column("buyer_type", sa.Text(), nullable=True),
        sa.Column("preferred_channel", sa.Text(), nullable=True),
        sa.Column("initial_strategy", sa.Text(), nullable=True),
        sa.Column("scorecard", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("gates", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_radar_candidates_slug"),
    )
    op.create_index("ix_radar_candidates_maturity", "radar_candidates", ["maturity"], unique=False)
    op.create_index("ix_radar_candidates_focus", "radar_candidates", ["focus"], unique=False)

    op.create_table(
        "radar_signals",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'new'")),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('new', 'triaged', 'linked', 'discarded')",
            name="radar_signals_status_check",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["radar_candidates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_signals_status", "radar_signals", ["status", "created_at"], unique=False)

    op.create_table(
        "radar_prompts",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_radar_prompts_key"),
    )

    op.create_table(
        "radar_prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("filename_pattern", sa.Text(), nullable=True),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("langfuse_prompt_ref", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 1", name="radar_prompt_versions_version_check"),
        sa.ForeignKeyConstraint(["prompt_id"], ["radar_prompts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_id", "version", name="uq_radar_prompt_versions_prompt_version"),
    )
    op.create_index("ix_radar_prompt_versions_active", "radar_prompt_versions", ["prompt_id", "is_active"], unique=False)

    op.create_table(
        "radar_apply_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("prompt_version_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("recognized_format", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'received'")),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("applied_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('received', 'applied', 'rejected', 'partial')",
            name="radar_apply_logs_status_check",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["radar_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["prompt_id"], ["radar_prompts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["radar_prompt_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_apply_logs_created_at", "radar_apply_logs", ["created_at"], unique=False)

    op.create_table(
        "radar_file_imports",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("apply_log_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("payload_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'failed', 'duplicate')",
            name="radar_file_imports_status_check",
        ),
        sa.ForeignKeyConstraint(["apply_log_id"], ["radar_apply_logs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_file_imports_created_at", "radar_file_imports", ["created_at"], unique=False)

    op.create_table(
        "radar_config",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("key"),
    )

    radar_config_table = sa.table(
        "radar_config",
        sa.column("key", sa.Text()),
        sa.column("value", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        radar_config_table,
        [
            {
                "key": key,
                "value": values,
                "description": f"Radar taxonomy for {key}",
            }
            for key, values in RADAR_TAXONOMIES.items()
        ],
    )

    op.execute("CREATE TRIGGER radar_candidates_touch BEFORE UPDATE ON radar_candidates FOR EACH ROW EXECUTE FUNCTION touch_updated_at();")
    op.execute("CREATE TRIGGER radar_signals_touch BEFORE UPDATE ON radar_signals FOR EACH ROW EXECUTE FUNCTION touch_updated_at();")
    op.execute("CREATE TRIGGER radar_prompts_touch BEFORE UPDATE ON radar_prompts FOR EACH ROW EXECUTE FUNCTION touch_updated_at();")
    op.execute("CREATE TRIGGER radar_config_touch BEFORE UPDATE ON radar_config FOR EACH ROW EXECUTE FUNCTION touch_updated_at();")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS radar_config_touch ON radar_config;")
    op.execute("DROP TRIGGER IF EXISTS radar_prompts_touch ON radar_prompts;")
    op.execute("DROP TRIGGER IF EXISTS radar_signals_touch ON radar_signals;")
    op.execute("DROP TRIGGER IF EXISTS radar_candidates_touch ON radar_candidates;")

    op.drop_table("radar_config")
    op.drop_index("ix_radar_file_imports_created_at", table_name="radar_file_imports")
    op.drop_table("radar_file_imports")
    op.drop_index("ix_radar_apply_logs_created_at", table_name="radar_apply_logs")
    op.drop_table("radar_apply_logs")
    op.drop_index("ix_radar_prompt_versions_active", table_name="radar_prompt_versions")
    op.drop_table("radar_prompt_versions")
    op.drop_table("radar_prompts")
    op.drop_index("ix_radar_signals_status", table_name="radar_signals")
    op.drop_table("radar_signals")
    op.drop_index("ix_radar_candidates_focus", table_name="radar_candidates")
    op.drop_index("ix_radar_candidates_maturity", table_name="radar_candidates")
    op.drop_table("radar_candidates")
