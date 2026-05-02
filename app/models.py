from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


TASK_STATUSES = ("backlog", "ready", "progress", "blocked", "done")


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "(idea_id IS NOT NULL) OR (project_id IS NOT NULL) OR (candidate_id IS NOT NULL)",
            name="tasks_requires_owner",
        ),
        CheckConstraint(
            "status IN ('backlog', 'ready', 'progress', 'blocked', 'done')",
            name="tasks_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    idea_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ideas.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vertical_candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'backlog'"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    promoted_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('telegram', 'whatsapp', 'email', 'system')",
            name="notification_events_channel_check",
        ),
        CheckConstraint(
            "direction IN ('inbound', 'outbound', 'system')",
            name="notification_events_direction_check",
        ),
        CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'failed', 'read', 'received')",
            name="notification_events_delivery_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vertical_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    idea_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ideas.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RadarCandidate(Base):
    __tablename__ = "radar_candidates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    maturity: Mapped[str | None] = mapped_column(Text, nullable=True)
    build_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_horizon: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_return: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_channel: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    scorecard: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    gates: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    decision_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_research: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    kill_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarSignal(Base):
    __tablename__ = "radar_signals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'triaged', 'linked', 'discarded')",
            name="radar_signals_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'new'"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarPrompt(Base):
    __tablename__ = "radar_prompts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarPromptVersion(Base):
    __tablename__ = "radar_prompt_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="radar_prompt_versions_version_check"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    prompt_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    variables_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    filename_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    langfuse_prompt_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarPromptRun(Base):
    __tablename__ = "radar_prompt_runs"
    __table_args__ = (
        CheckConstraint(
            "target_tool IN ('chatgpt_web', 'claude_web', 'codex', 'other')",
            name="radar_prompt_runs_target_tool_check",
        ),
        CheckConstraint(
            "status IN ('created', 'copied', 'waiting_import', 'applied', 'cancelled', 'failed')",
            name="radar_prompt_runs_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    prompt_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_tool: Mapped[str] = mapped_column(Text, nullable=False)
    model_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'created'"))
    apply_log_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_apply_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarApplyLog(Base):
    __tablename__ = "radar_apply_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('applied', 'failed', 'dry_run')",
            name="radar_apply_logs_status_check",
        ),
        CheckConstraint(
            "source_type IN ('manual_paste', 'drag_drop', 'api', 'unknown')",
            name="radar_apply_logs_source_type_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unknown'"))
    recognized_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'failed'"))
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    applied_changes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarFileImport(Base):
    __tablename__ = "radar_file_imports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'applied', 'failed', 'duplicate')",
            name="radar_file_imports_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    apply_log_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_apply_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RadarEvidence(Base):
    __tablename__ = "radar_evidence"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    candidate_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("radar_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_accessed: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RadarConfig(Base):
    __tablename__ = "radar_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
