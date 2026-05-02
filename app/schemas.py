from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectStateUpsert(StrictModel):
    current_focus: str | None = None
    current_milestone: str | None = None
    roadmap_version: str | None = None
    roadmap_ref: str | None = None
    project_state_code: int | None = None
    next_step: str | None = None
    blockers: list[Any] | None = None
    open_questions: list[Any] | None = None
    last_run_id: UUID | None = None
    last_audit_id: UUID | None = None
    extra: dict[str, Any] | None = None


class ProjectPatch(StrictModel):
    status: Literal["active", "paused", "archived", "killed"] | None = None
    priority: int | None = None
    importance: int | None = None
    host_machine: str | None = None
    progress_pct: int | None = None

    @field_validator("host_machine")
    @classmethod
    def validate_host_machine(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 6:
            raise ValueError("priority must be between 1 and 6")
        return value

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 5:
            raise ValueError("importance must be between 1 and 5")
        return value

    @field_validator("progress_pct")
    @classmethod
    def validate_progress_pct(cls, value: int | None) -> int | None:
        if value is not None and not 0 <= value <= 100:
            raise ValueError("progress_pct must be between 0 and 100")
        return value


class RunCreate(StrictModel):
    project_id: str
    agent: Literal[
        "codex",
        "claude-code",
        "claude-chat",
        "manual",
        "auditor",
        "investigator",
        "other",
    ]
    agent_version: str | None = None
    mode: str | None = None
    prompt_ref: str | None = None
    worktree_path: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    summary: str | None = None
    files_touched: list[Any] = Field(default_factory=list)
    diff_stats: dict[str, Any] = Field(default_factory=dict)
    next_step_proposed: str | None = None
    cost_usd: Decimal | None = None
    langfuse_trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunPatch(StrictModel):
    agent_version: str | None = None
    mode: str | None = None
    prompt_ref: str | None = None
    worktree_path: str | None = None
    ended_at: datetime | None = None
    status: Literal["running", "completed", "failed", "cancelled"] | None = None
    summary: str | None = None
    files_touched: list[Any] | None = None
    diff_stats: dict[str, Any] | None = None
    next_step_proposed: str | None = None
    cost_usd: Decimal | None = None
    langfuse_trace_id: str | None = None
    metadata: dict[str, Any] | None = None


class HandoffCreate(StrictModel):
    project_id: str
    from_run_id: UUID | None = None
    from_actor: str
    to_actor: str
    reason: Literal[
        "needs-human-review",
        "blocked",
        "context-exhausted",
        "scope-change",
        "needs-clarification",
        "pass-to-implementer",
        "pass-to-reviewer",
        "other",
    ]
    message: str
    context_refs: list[Any] = Field(default_factory=list)
    status: Literal["open", "picked-up", "resolved", "abandoned"] = "open"


class HandoffPatch(StrictModel):
    message: str | None = None
    context_refs: list[Any] | None = None
    status: Literal["open", "picked-up", "resolved", "abandoned"] | None = None
    resolved_at: datetime | None = None
    resolved_by_run_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str | None) -> str | None:
        return normalize_text(value)


class DecisionCreate(StrictModel):
    project_id: str
    title: str
    context: str
    decision: str
    consequences: str | None = None
    alternatives: list[Any] = Field(default_factory=list)
    status: Literal["proposed", "active", "superseded", "rejected"] = "active"
    supersedes: UUID | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "context", "decision", "consequences", "created_by")
    @classmethod
    def validate_decision_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class DecisionSupersedeCreate(StrictModel):
    title: str
    context: str
    decision: str
    consequences: str | None = None
    status: Literal["proposed", "active"] = "active"
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "context", "decision", "consequences", "created_by")
    @classmethod
    def validate_supersede_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class IdeaCreate(StrictModel):
    project_id: str | None = None
    raw_text: str
    source: Literal["telegram", "whatsapp", "cli", "web", "other"]
    source_ref: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: Literal["new", "triaged", "promoted", "discarded"] = "new"
    promoted_to: str | None = None
    triage_notes: str | None = None
    triaged_at: datetime | None = None


class IdeaPatch(StrictModel):
    project_id: str | None = None
    source_ref: str | None = None
    tags: list[str] | None = None
    status: Literal["new", "triaged", "promoted", "discarded"] | None = None
    promoted_to: str | None = None
    triage_notes: str | None = None
    triaged_at: datetime | None = None

    @field_validator("source_ref", "promoted_to", "triage_notes")
    @classmethod
    def validate_patch_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("tags")
    @classmethod
    def validate_idea_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_tags(value)


class IdeaTriagePatch(StrictModel):
    project_id: str | None = None
    status: Literal["new", "triaged", "promoted", "discarded"] | None = None
    triage_notes: str | None = None
    promoted_to: str | None = None

    @field_validator("triage_notes", "promoted_to")
    @classmethod
    def validate_triage_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class DashboardResolveHandoff(StrictModel):
    handoff_id: UUID
    resolution_note: str | None = None

    @field_validator("resolution_note")
    @classmethod
    def validate_resolution_note(cls, value: str | None) -> str | None:
        return normalize_text(value)


class DashboardRequeueRequest(StrictModel):
    queue_id: UUID
    scheduled_for: datetime | date | None = None
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def validate_requeue_notes(cls, value: str | None) -> str | None:
        return normalize_text(value)


class NotificationEventCreate(StrictModel):
    channel: Literal["telegram", "whatsapp", "email", "system"]
    direction: Literal["inbound", "outbound", "system"]
    project_id: str | None = None
    candidate_id: UUID | None = None
    run_id: UUID | None = None
    idea_id: UUID | None = None
    task_id: UUID | None = None
    message_type: str | None = None
    external_ref: str | None = None
    delivery_status: Literal["pending", "delivered", "failed", "read", "received"] = "pending"
    summary: str | None = None
    payload_summary: dict[str, Any] | None = None
    error_summary: str | None = None
    delivered_at: datetime | None = None

    @field_validator("message_type", "external_ref", "summary", "error_summary")
    @classmethod
    def validate_notification_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


TaskStatus = Literal["backlog", "ready", "progress", "blocked", "done"]


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_tags(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None

    normalized: list[str] = []
    for item in value:
        cleaned = item.strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized


class TaskCreate(StrictModel):
    idea_id: UUID | None = None
    project_id: str | None = None
    candidate_id: UUID | None = None
    title: str
    description: str | None = None
    status: TaskStatus = "backlog"
    priority: int = 0
    position: int = 0
    tags: list[str] = Field(default_factory=list)
    promoted_to: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = normalize_text(value)
        if normalized is None:
            raise ValueError("title must not be empty")
        return normalized

    @field_validator("description", "promoted_to")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("priority", "position")
    @classmethod
    def validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be greater than or equal to 0")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value) or []

    @model_validator(mode="after")
    def validate_owner(self):
        if not any([self.idea_id, self.project_id, self.candidate_id]):
            raise ValueError("at least one of idea_id, project_id or candidate_id is required")
        return self


class TaskPatch(StrictModel):
    idea_id: UUID | None = None
    project_id: str | None = None
    candidate_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    position: int | None = None
    tags: list[str] | None = None
    promoted_to: str | None = None

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_text(value)
        if normalized is None:
            raise ValueError("title must not be empty")
        return normalized

    @field_validator("description", "promoted_to")
    @classmethod
    def validate_patch_optional_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("priority", "position")
    @classmethod
    def validate_patch_non_negative_int(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("must be greater than or equal to 0")
        return value

    @field_validator("tags")
    @classmethod
    def validate_patch_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_tags(value)


class CandidateCreate(StrictModel):
    slug: str
    name: str
    category: Literal[
        "small-quickwin",
        "medium-long",
        "unicorn",
        "learning",
        "profound-ai",
        "core-sub-vertical",
    ]
    parent_group: str | None = None
    hypothesis: str
    problem_desc: str | None = None
    kill_criteria: list[Any] = Field(default_factory=list)
    status: Literal["proposed", "investigating", "promising", "promoted", "killed", "paused"] = "proposed"
    priority: int | None = None
    importance: int | None = None
    estimated_size: int | None = None
    kill_verdict: dict[str, Any] | None = None
    promoted_to_project_id: str | None = None
    last_research_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug", "name", "parent_group", "hypothesis", "problem_desc")
    @classmethod
    def validate_candidate_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("priority")
    @classmethod
    def validate_candidate_priority(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 6:
            raise ValueError("priority must be between 1 and 6")
        return value

    @field_validator("importance")
    @classmethod
    def validate_candidate_importance(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 5:
            raise ValueError("importance must be between 1 and 5")
        return value

    @field_validator("estimated_size")
    @classmethod
    def validate_candidate_estimated_size(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 4:
            raise ValueError("estimated_size must be between 1 and 4")
        return value


class CandidatePatch(StrictModel):
    slug: str | None = None
    name: str | None = None
    category: Literal[
        "small-quickwin",
        "medium-long",
        "unicorn",
        "learning",
        "profound-ai",
        "core-sub-vertical",
    ] | None = None
    parent_group: str | None = None
    hypothesis: str | None = None
    problem_desc: str | None = None
    kill_criteria: list[Any] | None = None
    status: Literal["proposed", "investigating", "promising", "promoted", "killed", "paused"] | None = None
    priority: int | None = None
    importance: int | None = None
    estimated_size: int | None = None
    kill_verdict: dict[str, Any] | None = None
    promoted_to_project_id: str | None = None
    last_research_id: UUID | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("slug", "name", "parent_group", "hypothesis", "problem_desc")
    @classmethod
    def validate_candidate_patch_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("priority")
    @classmethod
    def validate_candidate_patch_priority(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 6:
            raise ValueError("priority must be between 1 and 6")
        return value

    @field_validator("importance")
    @classmethod
    def validate_candidate_patch_importance(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 5:
            raise ValueError("importance must be between 1 and 5")
        return value

    @field_validator("estimated_size")
    @classmethod
    def validate_candidate_patch_estimated_size(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 4:
            raise ValueError("estimated_size must be between 1 and 4")
        return value


class AgentRunRequest(StrictModel):
    target_type: Literal["project", "candidate"]
    target_id: str
    prompt_ref: str | None = None


class CandidatePromotionRequest(StrictModel):
    project_id: str
    name: str | None = None
    kind: Literal["core", "project", "vertical", "group"] = "project"
    parent_id: str | None = None
    repo_url: str | None = None
    repo_path: str | None = None
    worktree_path: str | None = None
    host_machine: str | None = None
    priority: int | None = None
    importance: int | None = None
    size_scope: int | None = None
    progress_pct: int | None = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchQueuePatch(StrictModel):
    scheduled_for: date | None = None
    recurrence: Literal["once", "daily", "weekly", "monthly"] | None = None
    status: Literal["pending", "in-progress", "done", "skipped"] | None = None
    last_run_at: datetime | None = None
    last_report_id: UUID | None = None
    notes: str | None = None


class RadarCandidateCreate(StrictModel):
    slug: str
    name: str
    summary: str | None = None
    hypothesis: str | None = None
    focus: str | None = None
    scope: str | None = None
    maturity: str | None = "candidate"
    build_level: str | None = None
    time_horizon: str | None = None
    expected_return: str | None = None
    dominant_risk: str | None = None
    validation_mode: str | None = None
    evidence_requirement: str | None = None
    buyer_type: str | None = None
    preferred_channel: str | None = None
    initial_strategy: str | None = None
    scorecard: dict[str, Any] = Field(default_factory=dict)
    gates: dict[str, Any] = Field(default_factory=dict)
    decision_memo: str | None = None
    next_research: dict[str, Any] = Field(default_factory=dict)
    kill_criteria: dict[str, Any] = Field(default_factory=dict)
    verdict: str | None = None
    priority: int | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "slug",
        "name",
        "summary",
        "hypothesis",
        "focus",
        "scope",
        "maturity",
        "build_level",
        "time_horizon",
        "expected_return",
        "dominant_risk",
        "validation_mode",
        "evidence_requirement",
        "buyer_type",
        "preferred_channel",
        "initial_strategy",
        "decision_memo",
        "verdict",
        "notes",
    )
    @classmethod
    def validate_candidate_text_fields(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("slug", "name")
    @classmethod
    def validate_required_candidate_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("must not be empty")
        return value

    @field_validator("priority")
    @classmethod
    def validate_candidate_priority(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("priority must be greater than or equal to 0")
        return value


class RadarCandidatePatch(StrictModel):
    slug: str | None = None
    name: str | None = None
    summary: str | None = None
    hypothesis: str | None = None
    focus: str | None = None
    scope: str | None = None
    maturity: str | None = None
    build_level: str | None = None
    time_horizon: str | None = None
    expected_return: str | None = None
    dominant_risk: str | None = None
    validation_mode: str | None = None
    evidence_requirement: str | None = None
    buyer_type: str | None = None
    preferred_channel: str | None = None
    initial_strategy: str | None = None
    scorecard: dict[str, Any] | None = None
    gates: dict[str, Any] | None = None
    decision_memo: str | None = None
    next_research: dict[str, Any] | None = None
    kill_criteria: dict[str, Any] | None = None
    verdict: str | None = None
    priority: int | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator(
        "slug",
        "name",
        "summary",
        "hypothesis",
        "focus",
        "scope",
        "maturity",
        "build_level",
        "time_horizon",
        "expected_return",
        "dominant_risk",
        "validation_mode",
        "evidence_requirement",
        "buyer_type",
        "preferred_channel",
        "initial_strategy",
        "decision_memo",
        "verdict",
        "notes",
    )
    @classmethod
    def validate_candidate_patch_text_fields(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("priority")
    @classmethod
    def validate_candidate_patch_priority(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("priority must be greater than or equal to 0")
        return value


class RadarSignalCreate(StrictModel):
    candidate_id: UUID | None = None
    source: str
    title: str
    summary: str | None = None
    status: Literal["new", "triaged", "linked", "discarded"] = "new"
    tags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "title", "summary")
    @classmethod
    def validate_signal_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("source", "title")
    @classmethod
    def validate_required_signal_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def validate_signal_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value) or []


class RadarSignalPatch(StrictModel):
    candidate_id: UUID | None = None
    source: str | None = None
    title: str | None = None
    summary: str | None = None
    status: Literal["new", "triaged", "linked", "discarded"] | None = None
    tags: list[str] | None = None
    raw_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("source", "title", "summary")
    @classmethod
    def validate_signal_patch_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("tags")
    @classmethod
    def validate_signal_patch_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_tags(value)


class RadarPromptCreate(StrictModel):
    key: str
    title: str
    prompt_type: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("key", "title", "prompt_type", "description")
    @classmethod
    def validate_prompt_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("key", "title", "prompt_type")
    @classmethod
    def validate_required_prompt_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("must not be empty")
        return value


class RadarPromptPatch(StrictModel):
    key: str | None = None
    title: str | None = None
    prompt_type: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("key", "title", "prompt_type", "description")
    @classmethod
    def validate_prompt_patch_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class RadarPromptVersionCreate(StrictModel):
    version: int | None = None
    body: str
    output_schema: dict[str, Any] = Field(default_factory=dict)
    variables_schema: dict[str, Any] | None = None
    filename_pattern: str | None = None
    changelog: str | None = None
    is_active: bool = False
    langfuse_prompt_ref: str | None = None
    system_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("body")
    @classmethod
    def validate_prompt_body(cls, value: str) -> str:
        normalized = normalize_text(value)
        if normalized is None:
            raise ValueError("body must not be empty")
        return normalized

    @field_validator("filename_pattern", "changelog", "langfuse_prompt_ref", "system_notes")
    @classmethod
    def validate_prompt_version_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("version")
    @classmethod
    def validate_prompt_version_number(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("version must be greater than or equal to 1")
        return value


class RadarPromptRender(StrictModel):
    candidate_id: UUID | None = None
    target_tool: Literal["chatgpt_web", "claude_web", "codex", "other"] = "chatgpt_web"
    model_label: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @field_validator("model_label", "notes")
    @classmethod
    def validate_prompt_render_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class RadarPromptRunPatch(StrictModel):
    status: Literal["created", "copied", "waiting_import", "applied", "cancelled", "failed"] | None = None
    model_label: str | None = None
    notes: str | None = None
    apply_log_id: UUID | None = None

    @field_validator("model_label", "notes")
    @classmethod
    def validate_prompt_run_patch_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class RadarConfigPut(StrictModel):
    value: dict[str, Any] | list[Any]
    description: str | None = None

    @field_validator("description")
    @classmethod
    def validate_config_description(cls, value: str | None) -> str | None:
        return normalize_text(value)


class RadarApplyJsonPayload(StrictModel):
    payload: dict[str, Any]


class RadarFileImportCreate(StrictModel):
    filename: str
    original_path: str | None = None
    stored_path: str | None = None
    file_hash: str
    status: Literal["pending", "processed", "failed", "duplicate"] = "pending"
    apply_log_id: UUID | None = None
    payload_summary: dict[str, Any] | None = None
    error_message: str | None = None

    @field_validator("filename", "original_path", "stored_path", "file_hash", "error_message")
    @classmethod
    def validate_file_import_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("filename", "file_hash")
    @classmethod
    def validate_required_file_import_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("must not be empty")
        return value


class RadarFileImportPatch(StrictModel):
    stored_path: str | None = None
    status: Literal["pending", "processed", "failed", "duplicate"] | None = None
    apply_log_id: UUID | None = None
    payload_summary: dict[str, Any] | None = None
    error_message: str | None = None
    processed_at: datetime | None = None

    @field_validator("stored_path", "error_message")
    @classmethod
    def validate_file_import_patch_text(cls, value: str | None) -> str | None:
        return normalize_text(value)


class RadarEvidenceCreate(StrictModel):
    kind: str
    title: str | None = None
    url: str | None = None
    source_name: str | None = None
    source_tier: str | None = None
    claim: str | None = None
    confidence: float | None = None
    date_accessed: datetime | None = None
    notes: str | None = None

    @field_validator("kind", "title", "url", "source_name", "source_tier", "claim", "notes")
    @classmethod
    def validate_evidence_text(cls, value: str | None) -> str | None:
        return normalize_text(value)

    @field_validator("kind")
    @classmethod
    def validate_required_kind(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("kind must not be empty")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value
