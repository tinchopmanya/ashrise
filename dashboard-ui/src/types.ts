export type HealthStatus = "ok" | "degraded" | "down" | "unknown";
export type TaskStatus = "backlog" | "ready" | "progress" | "blocked" | "done";

export type TaskCounts = {
  total: number;
  backlog: number;
  ready: number;
  progress: number;
  blocked: number;
  done: number;
};

export type OverviewResponse = {
  kpis: {
    active_projects: number;
    runs_today: number;
    open_handoffs: number;
    ideas_new: number;
    queue_due_today: number;
    candidates_ready_to_promote: number;
  };
  weekly_evolution: Array<{
    date: string;
    runs: number;
    handoffs_opened: number;
    handoffs_resolved: number;
    audits: number;
    ideas: number;
  }>;
  latest_runs: Array<{
    id: string;
    project_id: string;
    agent: string;
    mode: string | null;
    status: string;
    summary: string | null;
    started_at: string;
    ended_at: string | null;
    prompt_ref: string | null;
    langfuse_trace_id: string | null;
  }>;
  open_handoffs: Array<{
    id: string;
    project_id: string;
    from_actor: string;
    to_actor: string;
    reason: string;
    message: string | null;
    status: string;
    created_at: string;
    resolved_at: string | null;
  }>;
  latest_audits: Array<{
    id: string;
    project_id: string;
    verdict: string;
    confidence: number | null;
    summary: string | null;
    created_at: string;
  }>;
  health_summary: Record<
    "api" | "db" | "langfuse" | "telegram_bot" | "cron_scheduler",
    {
      status: HealthStatus;
      note: string | null;
    }
  >;
};

export type DashboardProject = {
  id: string;
  name: string;
  kind: string;
  parent_id: string | null;
  host_machine: string | null;
  status: string;
  priority: number | null;
  importance: number | null;
  size_scope: number | null;
  progress_pct: number | null;
  current_focus: string | null;
  current_milestone: string | null;
  next_step: string | null;
  last_run_at: string | null;
  last_audit_at: string | null;
  open_handoffs_count: number;
};

export type ProjectDetailResponse = {
  project: {
    id: string;
    name: string;
    kind: string;
    parent_id: string | null;
    host_machine: string | null;
    status: string;
    priority: number | null;
    importance: number | null;
    size_scope: number | null;
    progress_pct: number | null;
  };
  state: {
    current_focus: string | null;
    current_milestone: string | null;
    roadmap_ref: string | null;
    project_state_code: number | null;
    next_step: string | null;
    blockers: Array<Record<string, unknown>>;
    open_questions: Array<Record<string, unknown>>;
    updated_at: string | null;
  };
  latest_audit: {
    id: string;
    verdict: string;
    confidence: number | null;
    summary: string | null;
    findings: Array<Record<string, unknown>>;
    created_at: string;
  } | null;
  recent_runs: Array<{
    id: string;
    agent: string;
    mode: string | null;
    status: string;
    summary: string | null;
    started_at: string;
    ended_at: string | null;
    prompt_ref: string | null;
    langfuse_trace_id: string | null;
    files_touched: number | null;
    diff_stats: Record<string, unknown> | null;
  }>;
  open_handoffs: Array<{
    id: string;
    from_actor: string;
    to_actor: string;
    reason: string;
    message: string | null;
    status: string;
    created_at: string;
  }>;
  decisions: Array<{
    id: string;
    title: string;
    context: string | null;
    decision: string;
    consequences: string | null;
    status: string;
    supersedes: string | null;
    created_by: string | null;
    created_at: string;
  }>;
  related_research: Array<{
    id: string;
    slug: string;
    name: string;
    status: string;
    promoted_to_project_id: string | null;
  }>;
  related_ideas: Array<{
    id: string;
    raw_text: string;
    source: string;
    status: string;
    created_at: string;
  }>;
};

export type GraphNodeType = "project" | "run" | "handoff" | "decision" | "candidate" | "idea" | "task" | "audit";

export type ProjectGraphResponse = {
  nodes: Array<{
    id: string;
    type: GraphNodeType;
    label: string;
    color_hint: string | null;
    meta: Record<string, unknown>;
  }>;
  edges: Array<{
    from: string;
    to: string;
    kind: "produced" | "resolved_by" | "relates_to" | "promoted_from" | "blocks" | "audits" | "touches";
  }>;
};

export type ResearchOverviewResponse = {
  kpis: {
    ready_to_promote: number;
    queue_due_today: number;
    pending_queue_total: number;
  };
  ready_to_promote: Array<{
    id: string;
    slug: string;
    name: string;
    status: string;
    last_research: {
      id: string;
      verdict: string;
      confidence: number | null;
      summary: string | null;
      created_at: string;
    } | null;
  }>;
  candidates: Array<{
    id: string;
    slug: string;
    name: string;
    category: string | null;
    parent_group: string | null;
    hypothesis: string;
    problem_desc: string | null;
    status: string;
    priority: number | null;
    importance: number | null;
    estimated_size: number | null;
    kill_verdict: Record<string, unknown> | null;
    promoted_to_project_id: string | null;
    last_research: {
      id: string;
      verdict: string;
      confidence: number | null;
      summary: string | null;
      created_at: string;
    } | null;
  }>;
  queue: Array<{
    id: string;
    candidate_id: string | null;
    project_id: string | null;
    queue_type: string;
    priority: number | null;
    scheduled_for: string;
    status: string;
    last_run_at: string | null;
    notes: string | null;
  }>;
  recent_reports: Array<{
    id: string;
    candidate_id: string;
    verdict: string;
    confidence: number | null;
    summary: string | null;
    created_at: string;
  }>;
};

export type RunSummary = {
  id: string;
  project_id: string;
  project_name: string | null;
  agent: string;
  agent_version: string | null;
  mode: string | null;
  prompt_ref: string | null;
  worktree_path: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  summary: string | null;
  files_touched: string[] | null;
  files_touched_count: number;
  diff_stats: Record<string, unknown> | null;
  next_step_proposed: string | null;
  cost_usd: number | null;
  langfuse_trace_id: string | null;
};

export type RunDetail = RunSummary & {
  metadata: Record<string, unknown> | null;
};

export type AgentRunResponse = {
  target_type: "project" | "candidate";
  target_id: string;
  report_type: string;
  summary: string;
  run: {
    id: string;
    agent: string;
    status: string;
    summary: string | null;
    started_at: string;
    ended_at: string | null;
    langfuse_trace_id: string | null;
    metadata: Record<string, unknown> | null;
  };
  report: Record<string, unknown>;
};

export type LangfuseTraceItem = {
  run_id: string;
  project_id: string;
  project_name: string | null;
  agent: string;
  mode: string | null;
  status: string;
  summary: string | null;
  started_at: string;
  ended_at: string | null;
  prompt_ref: string | null;
  prompt_name: string | null;
  langfuse_trace_id: string | null;
  prompt_source: string | null;
  prompt_fallback: boolean;
  langfuse_status: string | null;
  langfuse_error: string | null;
};

export type LangfuseSummaryResponse = {
  langfuse_base_url: string | null;
  kpis: {
    observed_runs: number;
    unique_prompts: number;
    traced_runs: number;
    fallback_runs: number;
    error_runs: number;
  };
  prompt_sources: Array<{
    source: string;
    count: number;
  }>;
  langfuse_statuses: Array<{
    status: string;
    count: number;
  }>;
  recent_fallbacks: LangfuseTraceItem[];
  recent_errors: LangfuseTraceItem[];
};

export type LangfusePromptsResponse = {
  langfuse_base_url: string | null;
  items: Array<{
    prompt_ref: string;
    prompt_name: string | null;
    runs_count: number;
    last_used_at: string;
    last_project_id: string | null;
    last_project_name: string | null;
    last_prompt_source: string | null;
    last_prompt_fallback: boolean;
    last_langfuse_status: string | null;
    last_langfuse_error: string | null;
    last_trace_id: string | null;
  }>;
};

export type LangfuseTracesFilters = {
  project_id?: string;
  agent?: string;
  prompt_source?: string;
  langfuse_status?: string;
};

export type LangfuseTracesResponse = {
  langfuse_base_url: string | null;
  items: LangfuseTraceItem[];
};

export type ActivityKind =
  | "run"
  | "handoff"
  | "decision"
  | "audit"
  | "idea"
  | "task"
  | "research_report"
  | "notification";

export type ActivityFeedItem = {
  id: string;
  ts: string;
  kind: ActivityKind;
  title: string;
  summary: string | null;
  project_id: string | null;
  candidate_id: string | null;
  idea_id: string | null;
  task_id: string | null;
  run_id: string | null;
  status: string | null;
  verdict: string | null;
  actor: string | null;
  source: string | null;
  route: string | null;
};

export type ActivityFeedResponse = {
  items: ActivityFeedItem[];
  next_cursor: string | null;
};

export type ActivityFeedFilters = {
  kind?: string;
  project_id?: string;
  candidate_id?: string;
  status?: string;
  source?: string;
};

export type NotificationEventRecord = {
  id: string;
  channel: string;
  direction: string;
  project_id: string | null;
  project_name: string | null;
  candidate_id: string | null;
  candidate_name: string | null;
  run_id: string | null;
  idea_id: string | null;
  idea_title: string | null;
  task_id: string | null;
  task_title: string | null;
  message_type: string | null;
  external_ref: string | null;
  delivery_status: string;
  summary: string | null;
  payload_summary: Record<string, unknown>;
  error_summary: string | null;
  created_at: string;
  delivered_at: string | null;
};

export type DashboardNotificationsResponse = {
  summary: {
    total: number;
    telegram: number;
    inbound: number;
    outbound: number;
    delivered: number;
    failed: number;
  };
  items: NotificationEventRecord[];
};

export type TelegramSummaryResponse = {
  kpis: {
    total_events: number;
    inbound_events: number;
    outbound_events: number;
    delivered_events: number;
    failed_events: number;
  };
  message_types: Array<{
    message_type: string;
    count: number;
  }>;
  recent_events: NotificationEventRecord[];
};

export type SystemJobsResponse = {
  items: Array<{
    key: string;
    label: string;
    status: HealthStatus;
    note: string | null;
    last_run_at: string | null;
    last_success_at: string | null;
    signal_source: string;
  }>;
};

export type SystemIntegrationsResponse = {
  items: Array<{
    key: string;
    label: string;
    status: HealthStatus;
    note: string | null;
    last_activity_at: string | null;
    last_success_at: string | null;
    signal_source: string;
  }>;
};

export type DashboardRequeueInput = {
  queue_id: string;
  scheduled_for?: string | null;
  notes?: string | null;
};

export type ResearchQueueItem = ResearchOverviewResponse["queue"][number];

export type CandidatePromotionInput = {
  project_id: string;
  name?: string | null;
  kind?: "core" | "project" | "vertical" | "group";
  parent_id?: string | null;
  host_machine?: string | null;
};

export type CandidatePromotionResponse = {
  project: Record<string, unknown>;
  candidate: {
    id: string;
    status: string;
    promoted_to_project_id: string | null;
  };
  message: string;
};

export type HandoffSummary = {
  id: string;
  project_id: string;
  project_name: string | null;
  from_run_id: string | null;
  from_actor: string;
  to_actor: string;
  reason: string;
  message: string | null;
  context_refs: string[];
  status: string;
  created_at: string;
  resolved_at: string | null;
  resolved_by_run_id: string | null;
};

export type IdeaSummary = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  raw_text: string;
  source: string;
  source_ref: string | null;
  tags: string[];
  status: string;
  promoted_to: string | null;
  triage_notes: string | null;
  created_at: string;
  triaged_at: string | null;
  task_counts: TaskCounts;
  cross_links: string[];
};

export type IdeaTriageInput = {
  project_id?: string | null;
  status?: "new" | "triaged" | "promoted" | "discarded";
  triage_notes?: string | null;
  promoted_to?: string | null;
};

export type TaskRecord = {
  id: string;
  idea_id: string | null;
  project_id: string | null;
  candidate_id: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: number;
  position: number;
  tags: string[];
  promoted_to: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
};

export type IdeasOverviewResponse = {
  kpis: {
    total: number;
    new: number;
    triaged: number;
    promoted: number;
    discarded: number;
  };
  task_kpis: TaskCounts;
  sources: {
    telegram: number;
    whatsapp: number;
    cli: number;
    web: number;
    other: number;
  };
  counts_by_source: {
    telegram: number;
    whatsapp: number;
    cli: number;
    web: number;
    other: number;
  };
  ideas: IdeaSummary[];
};

export type IdeaWorkspaceResponse = {
  idea: IdeaSummary;
  tasks: TaskRecord[];
  sibling_ideas_in_same_tag: IdeaSummary[];
  suggested_next: string[];
};

export type BoardTaskCard = TaskRecord & {
  idea_summary: string | null;
  idea_title: string | null;
};

export type TasksBoardResponse = Record<TaskStatus, BoardTaskCard[]>;
export type TasksBoardFilters = {
  idea_id?: string;
  project_id?: string;
  candidate_id?: string;
};

export type TaskCreateInput = {
  idea_id?: string | null;
  project_id?: string | null;
  candidate_id?: string | null;
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: number;
  position?: number;
  tags?: string[];
  promoted_to?: string | null;
};

export type TaskPatchInput = Partial<TaskCreateInput>;

export type DecisionCreateInput = {
  project_id: string;
  title: string;
  context: string;
  decision: string;
  consequences?: string | null;
  status?: "proposed" | "active" | "superseded" | "rejected";
  created_by?: string | null;
};

export type DecisionSupersedeInput = {
  title: string;
  context: string;
  decision: string;
  consequences?: string | null;
  status?: "proposed" | "active";
  created_by?: string | null;
};

export type DecisionRecord = {
  id: string;
  project_id: string;
  title: string;
  context: string | null;
  decision: string;
  consequences: string | null;
  status: string;
  supersedes?: string | null;
  created_at: string;
  created_by: string | null;
};

export type ProjectStateInput = {
  current_focus?: string | null;
  current_milestone?: string | null;
  next_step?: string | null;
  blockers?: string[];
  open_questions?: string[];
};

export type ProjectPatchInput = {
  status?: "active" | "paused" | "archived" | "killed";
  priority?: number | null;
  importance?: number | null;
  host_machine?: string | null;
  progress_pct?: number | null;
};

export type CandidatePatchInput = {
  status?: "proposed" | "investigating" | "promising" | "promoted" | "killed" | "paused";
  priority?: number | null;
  importance?: number | null;
  estimated_size?: number | null;
  hypothesis?: string | null;
  problem_desc?: string | null;
};

export type SystemHealthResponse = Record<
  "api" | "db" | "langfuse" | "telegram_bot" | "cron_scheduler",
  {
    status: HealthStatus;
    note: string | null;
  }
>;
