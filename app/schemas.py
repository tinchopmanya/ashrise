from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
