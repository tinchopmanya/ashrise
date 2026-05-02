import { useDeferredValue, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  applyRadarJson,
  compareRadarPortfolioCandidates,
  createRadarCandidate,
  createRadarCandidateEvidence,
  createRadarPrompt,
  createRadarPromptVersion,
  cancelRadarPromptRun,
  deleteRadarEvidence,
  getActivityFeed,
  getRadarApplyLogs,
  getRadarCandidate,
  getRadarCandidateEvidence,
  getRadarCandidates,
  getRadarConfig,
  getRadarFileImports,
  getRadarCandidateLinks,
  getRadarPortfolioFocusScopeMatrix,
  getRadarPortfolioMaturityVerdictMatrix,
  getRadarPortfolioOverview,
  getRadarPortfolioRiskDistribution,
  getRadarPortfolioSelectionQueue,
  getRadarPromotionPreview,
  getRadarPrompt,
  getRadarPromptRuns,
  getRadarPrompts,
  getRadarPromptVersions,
  patchProject,
  createDecision,
  createTask,
  deleteTask,
  getIdeaWorkspace,
  getIdeasOverview,
  getLangfusePrompts,
  getLangfuseSummary,
  getLangfuseTraces,
  getNotificationDetail,
  getNotifications,
  getOpenHandoffs,
  getOverview,
  getProjectDetail,
  getProjectGraph,
  getProjects,
  getRecentRuns,
  getResearchOverview,
  getRunDetail,
  getSystemIntegrations,
  getSystemJobs,
  getTasksBoard,
  getTelegramSummary,
  getSystemHealth,
  promoteCandidate,
  promoteRadarCandidate,
  markRadarPromptRunCopied,
  requeueResearchQueue,
  renderRadarPromptVersion,
  resolveDashboardHandoff,
  runDashboardAgent,
  supersedeDecision,
  triageIdea,
  updateCandidate,
  updateProjectState,
  updateRadarCandidate,
  updateTask,
} from "./api";
import type {
  ActivityFeedItem,
  ActivityFeedResponse,
  AgentRunResponse,
  CandidatePatchInput,
  CandidatePromotionResponse,
  DashboardProject,
  DecisionRecord,
  DashboardNotificationsResponse,
  HandoffSummary,
  HealthStatus,
  IdeaWorkspaceResponse,
  IdeasOverviewResponse,
  LangfusePromptsResponse,
  LangfuseSummaryResponse,
  LangfuseTraceItem,
  LangfuseTracesResponse,
  NotificationEventRecord,
  OverviewResponse,
  ProjectGraphResponse,
  ProjectDetailResponse,
  ResearchOverviewResponse,
  ResearchQueueItem,
  RunDetail,
  RunSummary,
  RadarApplyLog,
  RadarApplyResult,
  RadarCandidate,
  RadarConfigItem,
  RadarEvidence,
  RadarFileImport,
  RadarCandidateLink,
  RadarPortfolioCandidate,
  RadarPortfolioMatrix,
  RadarPromotionPreview,
  RadarPrompt,
  RadarPromptRenderResult,
  RadarPromptRun,
  RadarPromptVersion,
  SystemHealthResponse,
  SystemIntegrationsResponse,
  SystemJobsResponse,
  TaskCounts,
  TaskRecord,
  TelegramSummaryResponse,
  TasksBoardResponse,
  TaskStatus,
} from "./types";

type ProjectTab = "summary" | "graph" | "runs" | "handoffs" | "decisions" | "audit";
type IdeasSubview = "tree" | "tasks" | "board";

const navItems = [
  { to: "/dashboard", label: "Overview", caption: "Core pulse" },
  { to: "/dashboard/activity", label: "Activity", caption: "One feed, real signals" },
  { to: "/radar", label: "Radar", caption: "Discovery workbench" },
  { to: "/dashboard/projects", label: "Projects", caption: "Read-only fleet" },
  { to: "/dashboard/runs", label: "Runs", caption: "Recent activity" },
  { to: "/dashboard/handoffs", label: "Handoffs", caption: "Inbox by actor" },
  { to: "/dashboard/ideas", label: "Ideas", caption: "Workspace + tasks" },
  { to: "/dashboard/research", label: "Research", caption: "Pipeline + queue" },
  { to: "/dashboard/langfuse", label: "Prompts & Traces", caption: "Langfuse read-only" },
  { to: "/dashboard/notifications", label: "Notifications", caption: "Telegram history" },
  { to: "/dashboard/system", label: "System", caption: "Health + jobs" },
] as const;

const taskStatusOrder: TaskStatus[] = ["backlog", "ready", "progress", "blocked", "done"];
const taskStatusLabels: Record<TaskStatus, string> = {
  backlog: "Backlog",
  ready: "Ready",
  progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};

const ideasSubviewOptions: Array<{ value: IdeasSubview; label: string }> = [
  { value: "tree", label: "Tree + detail" },
  { value: "tasks", label: "Tasks" },
  { value: "board", label: "Board" },
];

const activityKindOptions = [
  { value: "", label: "Todos los kinds" },
  { value: "run", label: "Runs" },
  { value: "handoff", label: "Handoffs" },
  { value: "decision", label: "Decisions" },
  { value: "audit", label: "Audits" },
  { value: "idea", label: "Ideas" },
  { value: "task", label: "Tasks" },
  { value: "research_report", label: "Research reports" },
  { value: "notification", label: "Notifications" },
] as const;

const activityFilterKeys = ["kind", "project_id", "candidate_id", "status", "source", "q"] as const;
const activitySavedViewsStorageKey = "ashrise.dashboard.activity.savedViews";

type ActivitySavedView = {
  id: string;
  name: string;
  filters: Record<string, string>;
  queryString: string;
  createdAt: string;
};

const healthLabels: Record<string, string> = {
  api: "API",
  db: "DB",
  langfuse: "Langfuse",
  telegram_bot: "Telegram Bot",
  cron_scheduler: "Cron Scheduler",
};

const statusTone: Record<string, string> = {
  active: "good",
  paused: "muted",
  archived: "muted",
  killed: "bad",
  running: "accent",
  completed: "good",
  failed: "bad",
  cancelled: "muted",
  open: "accent",
  resolved: "good",
  "picked-up": "accent",
  abandoned: "bad",
  keep: "good",
  adjust: "warning",
  "pivot-lite": "accent",
  stop: "bad",
  promising: "good",
  investigating: "accent",
  proposed: "muted",
  ready_to_promote: "good",
  promoted: "good",
  killed_candidate: "bad",
  "in-progress": "accent",
  skipped: "muted",
  advance: "good",
  iterate: "warning",
  split: "accent",
  park: "muted",
  kill: "bad",
  traced: "good",
  fallback: "warning",
  "trace-error": "bad",
  langfuse: "good",
  "langfuse-fallback": "warning",
  "repo-local": "muted",
  backlog: "muted",
  ready: "warning",
  progress: "accent",
  blocked: "bad",
  done: "good",
  new: "accent",
  triaged: "warning",
  discarded: "muted",
  ok: "good",
  degraded: "warning",
  down: "bad",
  unknown: "muted",
  delivered: "good",
  received: "accent",
  pending: "warning",
  read: "good",
};

const healthTone: Record<HealthStatus, string> = {
  ok: "good",
  degraded: "warning",
  down: "bad",
  unknown: "muted",
};

const chartConfig = [
  { key: "runs", label: "Runs", color: "var(--accent)" },
  { key: "handoffs_opened", label: "Handoffs opened", color: "var(--accent-2)" },
  { key: "handoffs_resolved", label: "Handoffs resolved", color: "var(--green)" },
  { key: "audits", label: "Audits", color: "var(--pink)" },
  { key: "ideas", label: "Ideas", color: "var(--amber)" },
] as const;

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("es-UY", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("es-UY", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function formatDateInput(value: string | null) {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

function stringifyStructuredItem(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const primary = record.text || record.title || record.label || record.id || record.question;
    if (typeof primary === "string") {
      return primary;
    }
    return JSON.stringify(record);
  }
  return String(value);
}

function formatStructuredListForTextarea(items: unknown[]) {
  return items.map((item) => stringifyStructuredItem(item)).join("\n");
}

function parseMultilineListInput(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function formatCompactDate(value: string) {
  return new Intl.DateTimeFormat("es-UY", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function formatNumber(value: number | null) {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("es-UY").format(value);
}

function activityKindLabel(value: string) {
  if (value === "research_report") {
    return "Research report";
  }
  return sentenceCase(value);
}

function activityItemSubject(item: ActivityFeedItem) {
  if (item.project_id) {
    return item.project_id;
  }
  if (item.candidate_id) {
    return item.candidate_id;
  }
  if (item.idea_id) {
    return item.idea_id;
  }
  if (item.task_id) {
    return item.task_id;
  }
  return "—";
}

function pickActivityFilters(searchParams: URLSearchParams) {
  return Object.fromEntries(
    activityFilterKeys.map((key) => [key, searchParams.get(key) ?? ""]),
  ) as Record<(typeof activityFilterKeys)[number], string>;
}

function normalizeActivityQueryString(filters: Record<string, string>) {
  const params = new URLSearchParams();
  activityFilterKeys.forEach((key) => {
    const value = filters[key];
    if (value) {
      params.set(key, value);
    }
  });
  return params.toString();
}

function readActivitySavedViews() {
  if (typeof window === "undefined") {
    return [] as ActivitySavedView[];
  }
  try {
    const raw = window.localStorage.getItem(activitySavedViewsStorageKey);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is ActivitySavedView => {
      return Boolean(
        item &&
          typeof item === "object" &&
          typeof item.id === "string" &&
          typeof item.name === "string" &&
          typeof item.queryString === "string" &&
          typeof item.createdAt === "string" &&
          item.filters &&
          typeof item.filters === "object",
      );
    });
  } catch {
    return [];
  }
}

function writeActivitySavedViews(views: ActivitySavedView[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(activitySavedViewsStorageKey, JSON.stringify(views));
}

function isLiveStatus(status: string) {
  return status === "running";
}

function toneForStatus(status: string) {
  return statusTone[status] || "muted";
}

function toneForHealth(status: HealthStatus) {
  return healthTone[status];
}

function sentenceCase(value: string) {
  return value.split("-").join(" ");
}

function formatCurrency(value: number | null) {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("es-UY", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

function truncateText(value: string, maxLength = 140) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}...`;
}

function prettyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function AppShell({ children, title, subtitle }: { children: React.ReactNode; title: string; subtitle: string }) {
  const location = useLocation();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand reveal" style={{ "--stagger": 0 } as React.CSSProperties}>
          <div className="brand-mark">A</div>
            <div>
              <div className="eyebrow">Ashrise</div>
              <h1>Dashboard F7B</h1>
            </div>
          </div>

        <nav className="nav-list">
          {navItems.map((item, index) => {
            const active =
              item.to === "/dashboard"
                ? location.pathname === item.to
                : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
            return (
              <Link
                key={item.to}
                className={`nav-card reveal ${active ? "active" : ""}`}
                style={{ "--stagger": index + 1 } as React.CSSProperties}
                to={item.to}
              >
                <span className="nav-label">{item.label}</span>
                <span className="nav-caption">{item.caption}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-note reveal" style={{ "--stagger": 9 } as React.CSSProperties}>
          <span className="eyebrow">Phase 7B</span>
          <p>Activity suma saved views locales sobre filtros persistidos en URL para volver rápido a lecturas útiles del sistema.</p>
        </div>
      </aside>

      <main className="content">
        <header className="page-header">
          <div>
            <span className="eyebrow">Desktop control room</span>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
        </header>
        <div className="page-body">{children}</div>
      </main>
    </div>
  );
}

function StateScreen({
  title,
  body,
  tone = "muted",
}: {
  title: string;
  body: string;
  tone?: "muted" | "bad";
}) {
  return (
    <section className={`state-screen ${tone}`}>
      <div className="state-icon" />
      <h3>{title}</h3>
      <p>{body}</p>
    </section>
  );
}

function Section({
  title,
  eyebrow,
  aside,
  children,
  stagger = 0,
}: {
  title: string;
  eyebrow?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  stagger?: number;
}) {
  return (
    <section className="panel reveal" style={{ "--stagger": stagger } as React.CSSProperties}>
      <div className="section-head">
        <div>
          {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
          <h3>{title}</h3>
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

function SkeletonBlock({ height = 88 }: { height?: number }) {
  return <div className="skeleton-block" style={{ height }} />;
}

function StatusChip({ value, live = false }: { value: string; live?: boolean }) {
  return (
    <span className={`status-chip ${toneForStatus(value)} ${live ? "live" : ""}`}>
      <span className="status-dot" />
      {sentenceCase(value)}
    </span>
  );
}

function ProgressRing({ value }: { value: number | null }) {
  const safeValue = Math.max(0, Math.min(100, value ?? 0));
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (circumference * safeValue) / 100;

  return (
    <div className="ring-wrap">
      <svg className="progress-ring" viewBox="0 0 140 140" aria-hidden="true">
        <circle className="progress-ring-track" cx="70" cy="70" r={radius} />
        <circle
          className="progress-ring-fill"
          cx="70"
          cy="70"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="ring-copy">
        <span className="ring-value">{safeValue}%</span>
        <span className="ring-label">progress</span>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  note,
  live = false,
  stagger,
}: {
  label: string;
  value: number;
  note: string;
  live?: boolean;
  stagger: number;
}) {
  return (
    <article className={`kpi-card reveal ${live ? "live" : ""}`} style={{ "--stagger": stagger } as React.CSSProperties}>
      <span className="eyebrow">{label}</span>
      <strong>{formatNumber(value)}</strong>
      <p>{note}</p>
    </article>
  );
}

function HealthSummaryGrid({ data }: { data: SystemHealthResponse }) {
  return (
    <div className="health-grid">
      {Object.entries(data).map(([key, service], index) => (
        <article className="health-chip reveal" key={key} style={{ "--stagger": index } as React.CSSProperties}>
          <span className="eyebrow">{healthLabels[key]}</span>
          <div className={`health-state ${toneForHealth(service.status)}`}>
            <span className="status-dot" />
            {service.status}
          </div>
          <p>{service.note || "probe OK"}</p>
        </article>
      ))}
    </div>
  );
}

function KeyValueList({ items }: { items: Array<{ label: string; value: React.ReactNode }> }) {
  return (
    <dl className="key-value-list">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function OverviewPage() {
  const query = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: getOverview,
  });

  if (query.isLoading) {
    return (
      <AppShell title="Overview" subtitle="Estado general de la flota, actividad semanal y salud de servicios.">
        <div className="dashboard-grid">
          <div className="kpi-grid">
            {Array.from({ length: 6 }).map((_, index) => (
              <SkeletonBlock key={index} height={130} />
            ))}
          </div>
          <SkeletonBlock height={340} />
          <SkeletonBlock height={320} />
        </div>
      </AppShell>
    );
  }

  if (query.isError) {
    return (
      <AppShell title="Overview" subtitle="Estado general de la flota, actividad semanal y salud de servicios.">
        <StateScreen title="No pude cargar el overview" body={query.error.message} tone="bad" />
      </AppShell>
    );
  }

  const data = query.data as OverviewResponse;

  return (
    <AppShell title="Overview" subtitle="Estado general de la flota, actividad semanal y salud de servicios.">
      <div className="kpi-grid">
        <KpiCard label="Active projects" value={data.kpis.active_projects} note="projects con status active" stagger={0} />
        <KpiCard label="Runs today" value={data.kpis.runs_today} note="corridas abiertas hoy en Montevideo" stagger={1} live={data.kpis.runs_today > 0} />
        <KpiCard label="Open handoffs" value={data.kpis.open_handoffs} note="cola de coordinación vigente" stagger={2} />
        <KpiCard label="Ideas new" value={data.kpis.ideas_new} note="capturas pendientes de triage" stagger={3} />
        <KpiCard label="Queue due today" value={data.kpis.queue_due_today} note="research pendiente para hoy" stagger={4} />
        <KpiCard label="Ready to promote" value={data.kpis.candidates_ready_to_promote} note="candidatas listas en read-only" stagger={5} />
      </div>

      <div className="dashboard-grid">
        <Section title="Weekly evolution" eyebrow="Last 7 days" stagger={6}>
          {data.weekly_evolution.length === 0 ? (
            <StateScreen title="Sin datos semanales" body="Todavía no hay buckets para graficar." />
          ) : (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={data.weekly_evolution}>
                  <defs>
                    {chartConfig.map((series) => (
                      <linearGradient key={series.key} id={`gradient-${series.key}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={series.color} stopOpacity={0.38} />
                        <stop offset="95%" stopColor={series.color} stopOpacity={0.02} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid stroke="rgba(101, 123, 163, 0.14)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={formatCompactDate} stroke="rgba(212, 222, 241, 0.56)" />
                  <YAxis allowDecimals={false} stroke="rgba(212, 222, 241, 0.56)" />
                  <Tooltip
                    contentStyle={{
                      background: "var(--bg-3)",
                      border: "1px solid var(--border)",
                      borderRadius: 14,
                      color: "var(--ink)",
                    }}
                    labelFormatter={(value) => formatCompactDate(String(value))}
                  />
                  {chartConfig.map((series) => (
                    <Area
                      key={series.key}
                      type="monotone"
                      dataKey={series.key}
                      stackId="activity"
                      stroke={series.color}
                      fill={`url(#gradient-${series.key})`}
                      strokeWidth={2}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>

        <Section title="Health chips" eyebrow="System health" stagger={7}>
          <HealthSummaryGrid data={data.health_summary} />
        </Section>

        <Section title="Latest runs" eyebrow="Top 5" stagger={8}>
          {data.latest_runs.length === 0 ? (
            <StateScreen title="Sin runs recientes" body="Todavía no hay ejecuciones para mostrar." />
          ) : (
            <div className="stack-list">
              {data.latest_runs.map((run, index) => (
                <article className="list-card reveal" key={run.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <h4>{run.project_id}</h4>
                      <p>{run.summary || "Run sin summary todavía."}</p>
                    </div>
                    <StatusChip value={run.status} live={isLiveStatus(run.status)} />
                  </div>
                  <KeyValueList
                    items={[
                      { label: "agent", value: run.agent },
                      { label: "mode", value: run.mode || "—" },
                      { label: "started", value: formatDateTime(run.started_at) },
                      { label: "trace", value: run.langfuse_trace_id || "—" },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Open handoffs" eyebrow="Top 3" stagger={9}>
          {data.open_handoffs.length === 0 ? (
            <StateScreen title="Inbox limpio" body="No hay handoffs abiertos ahora mismo." />
          ) : (
            <div className="stack-list">
              {data.open_handoffs.map((handoff, index) => (
                <article className="list-card reveal" key={handoff.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <h4>{handoff.project_id}</h4>
                      <p>{handoff.message || "Sin mensaje adjunto."}</p>
                    </div>
                    <StatusChip value={handoff.status} />
                  </div>
                  <KeyValueList
                    items={[
                      { label: "from", value: handoff.from_actor },
                      { label: "to", value: handoff.to_actor },
                      { label: "reason", value: sentenceCase(handoff.reason) },
                      { label: "created", value: formatDateTime(handoff.created_at) },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Latest audits" eyebrow="Top 3" stagger={10}>
          {data.latest_audits.length === 0 ? (
            <StateScreen title="Sin auditorías recientes" body="Todavía no hay reportes para resumir." />
          ) : (
            <div className="stack-list">
              {data.latest_audits.map((audit, index) => (
                <article className="list-card reveal" key={audit.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <h4>{audit.project_id}</h4>
                      <p>{audit.summary || "Sin summary registrado."}</p>
                    </div>
                    <StatusChip value={audit.verdict} />
                  </div>
                  <KeyValueList
                    items={[
                      { label: "confidence", value: audit.confidence === null ? "—" : `${Math.round(audit.confidence * 100)}%` },
                      { label: "created", value: formatDateTime(audit.created_at) },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>
    </AppShell>
  );
}

function ProjectsPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [hostMachine, setHostMachine] = useState("");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);

  const filters = {
    status,
    kind,
    host_machine: hostMachine,
    q: deferredSearch.trim(),
  };

  const query = useQuery({
    queryKey: ["dashboard-projects", status, kind, hostMachine, deferredSearch.trim()],
    queryFn: () => getProjects(filters),
  });
  const projects = query.data ?? [];

  return (
    <AppShell title="Projects" subtitle="Vista agregada de proyectos activos y pausados, con foco actual y próximos pasos.">
      <Section title="Fleet" eyebrow="Read-only list" stagger={0}>
        <div className="filters">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre" />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Todos los status</option>
            <option value="active">active</option>
            <option value="paused">paused</option>
            <option value="archived">archived</option>
            <option value="killed">killed</option>
          </select>
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">Todos los kinds</option>
            <option value="core">core</option>
            <option value="project">project</option>
            <option value="vertical">vertical</option>
            <option value="group">group</option>
          </select>
          <input value={hostMachine} onChange={(event) => setHostMachine(event.target.value)} placeholder="Host machine" />
        </div>

        {query.isLoading ? (
          <div className="stack-list">
            {Array.from({ length: 5 }).map((_, index) => (
              <SkeletonBlock key={index} height={70} />
            ))}
          </div>
        ) : query.isError ? (
          <StateScreen title="No pude cargar los projects" body={query.error.message} tone="bad" />
        ) : projects.length === 0 ? (
          <StateScreen title="No hay proyectos para ese filtro" body="Probá limpiar filtros o ajustar la búsqueda." />
        ) : (
          <ProjectsTable
            projects={projects}
            onRowClick={(project) => navigate(`/dashboard/projects/${project.id}`)}
          />
        )}
      </Section>
    </AppShell>
  );
}

function ProjectsTable({
  projects,
  onRowClick,
}: {
  projects: DashboardProject[];
  onRowClick: (project: DashboardProject) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>name</th>
            <th>kind</th>
            <th>status</th>
            <th>host machine</th>
            <th>current focus</th>
            <th>next step</th>
            <th>progress</th>
            <th>last run</th>
            <th>last audit</th>
            <th>open handoffs</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project, index) => (
            <tr
              key={project.id}
              className="reveal"
              style={{ "--stagger": index } as React.CSSProperties}
              onClick={() => onRowClick(project)}
            >
              <td>
                <div className="cell-title">{project.name}</div>
                <div className="cell-subtitle">{project.id}</div>
              </td>
              <td>{project.kind}</td>
              <td>
                <StatusChip value={project.status} />
              </td>
              <td>{project.host_machine || "—"}</td>
              <td>{project.current_focus || "—"}</td>
              <td>{project.next_step || "—"}</td>
              <td>
                <div className="progress-bar">
                  <span style={{ width: `${project.progress_pct ?? 0}%` }} />
                </div>
                <div className="cell-subtitle">{formatNumber(project.progress_pct)}%</div>
              </td>
              <td>{formatDateTime(project.last_run_at)}</td>
              <td>{formatDateTime(project.last_audit_at)}</td>
              <td>{project.open_handoffs_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type GraphPoint = { x: number; y: number };

const graphViewBox = { minX: -680, minY: -440, width: 1360, height: 880 };
const graphTypeOrder: ProjectGraphResponse["nodes"][number]["type"][] = [
  "run",
  "handoff",
  "decision",
  "audit",
  "candidate",
  "idea",
  "task",
];
const graphRingRadius: Record<ProjectGraphResponse["nodes"][number]["type"], number> = {
  project: 0,
  run: 220,
  handoff: 300,
  decision: 380,
  audit: 380,
  candidate: 460,
  idea: 540,
  task: 620,
};
const graphNodeRadius: Record<ProjectGraphResponse["nodes"][number]["type"], number> = {
  project: 42,
  run: 26,
  handoff: 24,
  decision: 24,
  candidate: 24,
  idea: 23,
  task: 21,
  audit: 24,
};

function graphColor(colorHint: string | null | undefined) {
  if (colorHint === "good" || colorHint === "green") return "var(--green)";
  if (colorHint === "warning" || colorHint === "amber") return "var(--amber)";
  if (colorHint === "bad" || colorHint === "red") return "var(--red)";
  if (colorHint === "pink") return "var(--pink)";
  if (colorHint === "accent-2") return "var(--accent-2)";
  return "var(--accent)";
}

function graphPointFromEvent(event: PointerEvent | React.PointerEvent, svg: SVGSVGElement, pan: GraphPoint, scale: number) {
  const rect = svg.getBoundingClientRect();
  const svgX = ((event.clientX - rect.left) / rect.width) * graphViewBox.width + graphViewBox.minX;
  const svgY = ((event.clientY - rect.top) / rect.height) * graphViewBox.height + graphViewBox.minY;
  return {
    x: (svgX - pan.x) / scale,
    y: (svgY - pan.y) / scale,
  };
}

function radialGraphPositions(graph: ProjectGraphResponse): Record<string, GraphPoint> {
  const positions: Record<string, GraphPoint> = {};
  const centerNode = graph.nodes.find((node) => node.type === "project");
  if (centerNode) {
    positions[centerNode.id] = { x: 0, y: 0 };
  }

  for (const type of graphTypeOrder) {
    const bucket = graph.nodes.filter((node) => node.type === type);
    if (!bucket.length) {
      continue;
    }
    const ring = graphRingRadius[type];
    const step = (Math.PI * 2) / bucket.length;
    const phase = type === "run" ? -Math.PI / 2 : type === "candidate" ? Math.PI / 3 : 0;
    bucket.forEach((node, index) => {
      const angle = phase + step * index;
      positions[node.id] = {
        x: Math.cos(angle) * ring,
        y: Math.sin(angle) * ring,
      };
    });
  }

  return positions;
}

function graphNodeMetaItems(node: ProjectGraphResponse["nodes"][number] | null) {
  if (!node) {
    return [];
  }

  return Object.entries(node.meta).map(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return { label: key, value: "-" };
    }
    if (typeof value === "string") {
      return { label: key, value: key.includes("_at") ? formatDateTime(value) : value };
    }
    if (typeof value === "number") {
      return { label: key, value };
    }
    return { label: key, value: JSON.stringify(value) };
  });
}

function ProjectGraphTab({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName: string;
}) {
  const graphQuery = useQuery({
    queryKey: ["dashboard-project-graph", projectId],
    queryFn: () => getProjectGraph(projectId),
  });
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragStateRef = useRef<
    | {
        type: "node";
        nodeId: string;
      }
    | {
        type: "pan";
        pointerX: number;
        pointerY: number;
        panX: number;
        panY: number;
      }
    | null
  >(null);
  const [pan, setPan] = useState<GraphPoint>({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [positions, setPositions] = useState<Record<string, GraphPoint>>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const graph = graphQuery.data as ProjectGraphResponse | undefined;
  const selectedNode = graph?.nodes.find((node) => node.id === selectedNodeId) || graph?.nodes[0] || null;

  useEffect(() => {
    if (!graph) {
      return;
    }
    setPositions(radialGraphPositions(graph));
    setSelectedNodeId(graph.nodes[0]?.id || null);
    setPan({ x: 0, y: 0 });
    setScale(1);
  }, [graph]);

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      const dragState = dragStateRef.current;
      const svg = svgRef.current;
      if (!dragState || !svg) {
        return;
      }

      if (dragState.type === "node") {
        const nextPoint = graphPointFromEvent(event, svg, pan, scale);
        setPositions((current) => ({
          ...current,
          [dragState.nodeId]: nextPoint,
        }));
        return;
      }

      setPan({
        x: dragState.panX + ((event.clientX - dragState.pointerX) / svg.getBoundingClientRect().width) * graphViewBox.width,
        y: dragState.panY + ((event.clientY - dragState.pointerY) / svg.getBoundingClientRect().height) * graphViewBox.height,
      });
    }

    function handlePointerUp() {
      dragStateRef.current = null;
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [pan, scale]);

  if (graphQuery.isLoading) {
    return (
      <div className="detail-layout">
        <SkeletonBlock height={540} />
        <SkeletonBlock height={540} />
      </div>
    );
  }

  if (graphQuery.isError) {
    return <StateScreen title="No pude cargar el graph" body={graphQuery.error.message} tone="bad" />;
  }

  if (!graph || graph.nodes.length <= 1) {
    return (
      <StateScreen
        title="Sin suficientes relaciones"
        body="Este proyecto todavía no tiene suficientes runs, handoffs, decisions, research, ideas, tasks o audits para dibujar un grafo útil."
      />
    );
  }

  return (
    <div className="detail-layout graph-layout">
      <Section
        title="Project graph"
        eyebrow="Radial graph foundation"
        stagger={1}
        aside={<span className="meta-pill">{graph.nodes.length} nodes · {graph.edges.length} edges</span>}
      >
        <div className="graph-toolbar">
          <span className="meta-pill">drag node</span>
          <span className="meta-pill">drag background to pan</span>
          <span className="meta-pill">wheel to zoom</span>
        </div>

        <div className="graph-canvas-shell">
          <svg
            ref={svgRef}
            className="project-graph-canvas"
            viewBox={`${graphViewBox.minX} ${graphViewBox.minY} ${graphViewBox.width} ${graphViewBox.height}`}
            onPointerDown={(event) => {
              if (event.target === event.currentTarget) {
                dragStateRef.current = {
                  type: "pan",
                  pointerX: event.clientX,
                  pointerY: event.clientY,
                  panX: pan.x,
                  panY: pan.y,
                };
              }
            }}
            onWheel={(event) => {
              event.preventDefault();
              const delta = event.deltaY > 0 ? -0.08 : 0.08;
              setScale((current) => Math.max(0.55, Math.min(1.8, Number((current + delta).toFixed(2)))));
            }}
          >
            <defs>
              <linearGradient id="graph-edge-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.75" />
                <stop offset="100%" stopColor="var(--accent-2)" stopOpacity="0.28" />
              </linearGradient>
            </defs>

            <rect
              x={graphViewBox.minX}
              y={graphViewBox.minY}
              width={graphViewBox.width}
              height={graphViewBox.height}
              fill="transparent"
            />

            <g transform={`translate(${pan.x} ${pan.y}) scale(${scale})`}>
              {graph.edges.map((edge) => {
                const from = positions[edge.from];
                const to = positions[edge.to];
                if (!from || !to) {
                  return null;
                }
                const midX = (from.x + to.x) / 2;
                const midY = (from.y + to.y) / 2;
                const controlX = midX + (to.y - from.y) * 0.06;
                const controlY = midY - (to.x - from.x) * 0.06;
                return (
                  <g key={`${edge.from}-${edge.to}-${edge.kind}`}>
                    <path
                      d={`M ${from.x} ${from.y} Q ${controlX} ${controlY} ${to.x} ${to.y}`}
                      className="graph-edge"
                    />
                    <text x={midX} y={midY} className="graph-edge-label">
                      {edge.kind}
                    </text>
                  </g>
                );
              })}

              {graph.nodes.map((node) => {
                const point = positions[node.id] || { x: 0, y: 0 };
                const radius = graphNodeRadius[node.type];
                const active = selectedNode?.id === node.id;
                return (
                  <g
                    key={node.id}
                    className={`graph-node ${active ? "active" : ""}`}
                    transform={`translate(${point.x} ${point.y})`}
                    onPointerDown={(event) => {
                      event.stopPropagation();
                      setSelectedNodeId(node.id);
                      dragStateRef.current = {
                        type: "node",
                        nodeId: node.id,
                      };
                    }}
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedNodeId(node.id);
                    }}
                  >
                    <circle
                      r={radius + (active ? 6 : 0)}
                      className="graph-node-halo"
                      style={{ color: graphColor(node.color_hint) }}
                    />
                    <circle
                      r={radius}
                      className="graph-node-core"
                      style={{ color: graphColor(node.color_hint) }}
                    />
                    <text y={radius + 24} className="graph-node-label">
                      {truncateText(node.label, node.type === "project" ? 28 : 18)}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>

        <p className="panel-note">
          F3A deja un layout radial determinista como base estable. Mantiene SVG nativo, drag/pan/zoom y deja el force-directed para el siguiente corte si hace falta física real.
        </p>
      </Section>

      <Section title="Node detail" eyebrow="Selection panel" stagger={2}>
        {!selectedNode ? (
          <StateScreen title="Sin nodo seleccionado" body={`Elegí un nodo del grafo de ${projectName} para inspeccionar su metadata.`} />
        ) : (
          <div className="stack-list">
            <article className="list-card graph-node-detail-card">
              <div className="row spread">
                <div>
                  <div className="eyebrow">{selectedNode.type}</div>
                  <h4>{selectedNode.label}</h4>
                  <p>{selectedNode.id}</p>
                </div>
                <span className="meta-pill" style={{ borderColor: graphColor(selectedNode.color_hint), color: graphColor(selectedNode.color_hint) }}>
                  {selectedNode.type}
                </span>
              </div>
              <KeyValueList items={graphNodeMetaItems(selectedNode)} />
            </article>
          </div>
        )}
      </Section>
    </div>
  );
}

function ProjectDetailPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<ProjectTab>("summary");
  const [projectActionMessage, setProjectActionMessage] = useState<string | null>(null);
  const [projectActionError, setProjectActionError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["dashboard-project-detail", projectId],
    queryFn: () => getProjectDetail(projectId as string),
    enabled: Boolean(projectId),
  });

  const runAgentMutation = useMutation({
    mutationFn: () => {
      if (!projectId) {
        throw new Error("Missing project id");
      }
      return runDashboardAgent({ target_type: "project", target_id: projectId });
    },
    onSuccess: async (response: AgentRunResponse) => {
      setProjectActionError(null);
      setProjectActionMessage(
        `Run launched: ${response.run.agent} - ${response.run.status}${response.run.id ? ` - ${response.run.id}` : ""}.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-detail", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-graph", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-projects"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-runs"] }),
      ]);
    },
    onError: (error: Error) => {
      setProjectActionMessage(null);
      setProjectActionError(error.message);
    },
  });

  if (!projectId) {
    return <Navigate to="/dashboard/projects" replace />;
  }

  async function handleRunAgent() {
    if (!window.confirm(`Run agent now for ${query.data?.project.name || projectId}?`)) {
      return;
    }
    setProjectActionMessage(null);
    setProjectActionError(null);
    await runAgentMutation.mutateAsync();
  }

  if (query.isLoading) {
    return (
      <AppShell title="Project Detail" subtitle="Estado, grafo, runs, handoffs, decisiones y ultimo audit del proyecto.">
        <SkeletonBlock height={220} />
        <SkeletonBlock height={420} />
      </AppShell>
    );
  }

  if (query.isError) {
    return (
      <AppShell title="Project Detail" subtitle="Estado, grafo, runs, handoffs, decisiones y ultimo audit del proyecto.">
        <StateScreen title="No pude cargar el detalle" body={query.error.message} tone="bad" />
      </AppShell>
    );
  }

  const data = query.data as ProjectDetailResponse;

  return (
    <AppShell title={data.project.name} subtitle="Header operativo con graph, runs, handoffs, decisiones y primeras acciones seguras del dashboard.">
      <section className="hero-card reveal" style={{ "--stagger": 0 } as React.CSSProperties}>
        <div className="hero-copy">
          <div className="row">
            <StatusChip value={data.project.status} />
            <span className="meta-pill">{data.project.kind}</span>
            <span className="meta-pill">{data.project.host_machine || "host pending"}</span>
          </div>
          <h3>{data.project.name}</h3>
          <p>{data.state.current_focus || "Sin foco actual cargado todavia."}</p>
          <KeyValueList
            items={[
              { label: "current milestone", value: data.state.current_milestone || "-" },
              { label: "next step", value: data.state.next_step || "-" },
              { label: "roadmap ref", value: data.state.roadmap_ref || "-" },
              { label: "updated", value: formatDateTime(data.state.updated_at) },
            ]}
          />
          <div className="task-actions hero-actions">
            <button className="primary-button" disabled={runAgentMutation.isPending} onClick={handleRunAgent} type="button">
              {runAgentMutation.isPending ? "Running..." : "Run agent"}
            </button>
            {projectActionMessage ? <p className="form-success">{projectActionMessage}</p> : null}
            {projectActionError ? <p className="form-error">{projectActionError}</p> : null}
          </div>
        </div>
        <ProgressRing value={data.project.progress_pct} />
      </section>

      <div className="tabs">
        {(["summary", "graph", "runs", "handoffs", "decisions", "audit"] as ProjectTab[]).map((item) => (
          <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </div>

      {tab === "summary" ? <ProjectSummary data={data} /> : null}
      {tab === "graph" ? <ProjectGraphTab projectId={projectId} projectName={data.project.name} /> : null}
      {tab === "runs" ? <ProjectRuns data={data} /> : null}
      {tab === "handoffs" ? <ProjectHandoffs data={data} /> : null}
      {tab === "decisions" ? <ProjectDecisions data={data} /> : null}
      {tab === "audit" ? <ProjectAudit data={data} /> : null}
    </AppShell>
  );
}

function ProjectSummary({ data }: { data: ProjectDetailResponse }) {
  const queryClient = useQueryClient();
  const [editingState, setEditingState] = useState(false);
  const [editingMetadata, setEditingMetadata] = useState(false);
  const [stateMessage, setStateMessage] = useState<string | null>(null);
  const [stateError, setStateError] = useState<string | null>(null);
  const [metadataMessage, setMetadataMessage] = useState<string | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [stateDraft, setStateDraft] = useState({
    current_focus: data.state.current_focus || "",
    current_milestone: data.state.current_milestone || "",
    next_step: data.state.next_step || "",
    blockers: formatStructuredListForTextarea(data.state.blockers),
    open_questions: formatStructuredListForTextarea(data.state.open_questions),
  });
  const [metadataDraft, setMetadataDraft] = useState({
    status: data.project.status,
    priority: data.project.priority?.toString() || "",
    importance: data.project.importance?.toString() || "",
    host_machine: data.project.host_machine || "",
    progress_pct: data.project.progress_pct?.toString() || "",
  });

  useEffect(() => {
    setStateDraft({
      current_focus: data.state.current_focus || "",
      current_milestone: data.state.current_milestone || "",
      next_step: data.state.next_step || "",
      blockers: formatStructuredListForTextarea(data.state.blockers),
      open_questions: formatStructuredListForTextarea(data.state.open_questions),
    });
  }, [
    data.project.id,
    data.state.current_focus,
    data.state.current_milestone,
    data.state.next_step,
    data.state.blockers,
    data.state.open_questions,
  ]);

  useEffect(() => {
    setMetadataDraft({
      status: data.project.status,
      priority: data.project.priority?.toString() || "",
      importance: data.project.importance?.toString() || "",
      host_machine: data.project.host_machine || "",
      progress_pct: data.project.progress_pct?.toString() || "",
    });
  }, [
    data.project.id,
    data.project.status,
    data.project.priority,
    data.project.importance,
    data.project.host_machine,
    data.project.progress_pct,
  ]);

  async function invalidateProjectViews() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard-project-detail", data.project.id] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-project-graph", data.project.id] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-projects"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
    ]);
  }

  const stateMutation = useMutation({
    mutationFn: () =>
      updateProjectState(data.project.id, {
        current_focus: stateDraft.current_focus || null,
        current_milestone: stateDraft.current_milestone || null,
        next_step: stateDraft.next_step || null,
        blockers: parseMultilineListInput(stateDraft.blockers),
        open_questions: parseMultilineListInput(stateDraft.open_questions),
      }),
    onSuccess: async () => {
      setStateError(null);
      setStateMessage("Project state updated.");
      setEditingState(false);
      await invalidateProjectViews();
    },
    onError: (error: Error) => {
      setStateMessage(null);
      setStateError(error.message);
    },
  });

  const metadataMutation = useMutation({
    mutationFn: () =>
      patchProject(data.project.id, {
        status: metadataDraft.status as "active" | "paused" | "archived" | "killed",
        priority: metadataDraft.priority ? Number(metadataDraft.priority) : null,
        importance: metadataDraft.importance ? Number(metadataDraft.importance) : null,
        host_machine: metadataDraft.host_machine || null,
        progress_pct: metadataDraft.progress_pct ? Number(metadataDraft.progress_pct) : null,
      }),
    onSuccess: async () => {
      setMetadataError(null);
      setMetadataMessage("Project metadata updated.");
      setEditingMetadata(false);
      await invalidateProjectViews();
    },
    onError: (error: Error) => {
      setMetadataMessage(null);
      setMetadataError(error.message);
    },
  });

  async function handleSaveState(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStateMessage(null);
    setStateError(null);
    await stateMutation.mutateAsync();
  }

  async function handleSaveMetadata(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMetadataMessage(null);
    setMetadataError(null);
    await metadataMutation.mutateAsync();
  }

  return (
    <div className="dashboard-grid">
      <Section
        title="State summary"
        eyebrow="Summary + state"
        stagger={1}
        aside={
          <button className="secondary-button" onClick={() => setEditingState((current) => !current)} type="button">
            {editingState ? "Close editor" : "Edit state"}
          </button>
        }
      >
        <KeyValueList
          items={[
            { label: "project state code", value: data.state.project_state_code ?? "—" },
            { label: "blockers", value: data.state.blockers.length || "0" },
            { label: "open questions", value: data.state.open_questions.length || "0" },
            { label: "priority", value: data.project.priority ?? "—" },
            { label: "importance", value: data.project.importance ?? "—" },
            { label: "size scope", value: data.project.size_scope ?? "—" },
          ]}
        />
        <div className="pill-cluster">
          {data.state.blockers.length === 0 ? <span className="meta-pill">No blockers</span> : null}
          {data.state.blockers.map((item, index) => (
            <span className="meta-pill" key={`blocker-${index}`}>
              blocker · {String(item.id || index)}
            </span>
          ))}
          {data.state.open_questions.map((item, index) => (
            <span className="meta-pill" key={`question-${index}`}>
              question · {String(item.id || index)}
            </span>
          ))}
        </div>
        {editingState ? (
          <form className="task-form list-card" onSubmit={handleSaveState}>
            <div className="eyebrow">Edit state</div>
            <input
              value={stateDraft.current_focus}
              onChange={(event) => setStateDraft((current) => ({ ...current, current_focus: event.target.value }))}
              placeholder="Current focus"
            />
            <input
              value={stateDraft.current_milestone}
              onChange={(event) =>
                setStateDraft((current) => ({ ...current, current_milestone: event.target.value }))
              }
              placeholder="Current milestone"
            />
            <textarea
              rows={3}
              value={stateDraft.next_step}
              onChange={(event) => setStateDraft((current) => ({ ...current, next_step: event.target.value }))}
              placeholder="Next step"
            />
            <textarea
              rows={4}
              value={stateDraft.blockers}
              onChange={(event) => setStateDraft((current) => ({ ...current, blockers: event.target.value }))}
              placeholder="One blocker per line"
            />
            <textarea
              rows={4}
              value={stateDraft.open_questions}
              onChange={(event) => setStateDraft((current) => ({ ...current, open_questions: event.target.value }))}
              placeholder="One open question per line"
            />
            <div className="task-actions">
              <button className="primary-button" disabled={stateMutation.isPending} type="submit">
                {stateMutation.isPending ? "Saving..." : "Save state"}
              </button>
            </div>
          </form>
        ) : null}
        {stateMessage ? <p className="form-success">{stateMessage}</p> : null}
        {stateError ? <p className="form-error">{stateError}</p> : null}
      </Section>

      <Section
        title="Project metadata"
        eyebrow="Safe edit"
        stagger={2}
        aside={
          <button className="secondary-button" onClick={() => setEditingMetadata((current) => !current)} type="button">
            {editingMetadata ? "Close editor" : "Edit metadata"}
          </button>
        }
      >
        <KeyValueList
          items={[
            { label: "status", value: data.project.status },
            { label: "priority", value: data.project.priority ?? "-" },
            { label: "importance", value: data.project.importance ?? "-" },
            { label: "host machine", value: data.project.host_machine || "-" },
            { label: "progress pct", value: data.project.progress_pct ?? "-" },
          ]}
        />
        {editingMetadata ? (
          <form className="task-form list-card" onSubmit={handleSaveMetadata}>
            <div className="eyebrow">Edit project metadata</div>
            <div className="inline-form-grid">
              <select
                value={metadataDraft.status}
                onChange={(event) => setMetadataDraft((current) => ({ ...current, status: event.target.value }))}
              >
                <option value="active">active</option>
                <option value="paused">paused</option>
                <option value="archived">archived</option>
                <option value="killed">killed</option>
              </select>
              <input
                value={metadataDraft.host_machine}
                onChange={(event) => setMetadataDraft((current) => ({ ...current, host_machine: event.target.value }))}
                placeholder="host_machine"
              />
            </div>
            <div className="inline-form-grid">
              <input
                type="number"
                min={1}
                max={6}
                value={metadataDraft.priority}
                onChange={(event) => setMetadataDraft((current) => ({ ...current, priority: event.target.value }))}
                placeholder="priority"
              />
              <input
                type="number"
                min={1}
                max={5}
                value={metadataDraft.importance}
                onChange={(event) => setMetadataDraft((current) => ({ ...current, importance: event.target.value }))}
                placeholder="importance"
              />
            </div>
            <input
              type="number"
              min={0}
              max={100}
              value={metadataDraft.progress_pct}
              onChange={(event) => setMetadataDraft((current) => ({ ...current, progress_pct: event.target.value }))}
              placeholder="progress_pct"
            />
            <div className="task-actions">
              <button className="primary-button" disabled={metadataMutation.isPending} type="submit">
                {metadataMutation.isPending ? "Saving..." : "Save metadata"}
              </button>
            </div>
          </form>
        ) : null}
        {metadataMessage ? <p className="form-success">{metadataMessage}</p> : null}
        {metadataError ? <p className="form-error">{metadataError}</p> : null}
      </Section>

      <Section title="Latest audit snapshot" eyebrow="Audit" stagger={3}>
        {data.latest_audit ? (
          <div className="stack-list compact">
            <StatusChip value={data.latest_audit.verdict} />
            <p>{data.latest_audit.summary || "Sin summary."}</p>
            <KeyValueList
              items={[
                {
                  label: "confidence",
                  value:
                    data.latest_audit.confidence === null ? "—" : `${Math.round(data.latest_audit.confidence * 100)}%`,
                },
                { label: "created", value: formatDateTime(data.latest_audit.created_at) },
                { label: "findings", value: data.latest_audit.findings.length },
              ]}
            />
          </div>
        ) : (
          <StateScreen title="Sin audit reciente" body="Este proyecto todavía no tiene un audit cargado." />
        )}
      </Section>

      <Section title="Related research" eyebrow="Research" stagger={3}>
        {data.related_research.length === 0 ? (
          <StateScreen title="Sin research relacionado" body="No hay candidatas promovidas ligadas a este proyecto." />
        ) : (
          <div className="stack-list">
            {data.related_research.map((item, index) => (
              <article className="list-card reveal" key={item.id} style={{ "--stagger": index } as React.CSSProperties}>
                <div className="row spread">
                  <div>
                    <h4>{item.name}</h4>
                    <p>{item.slug}</p>
                  </div>
                  <StatusChip value={item.status} />
                </div>
              </article>
            ))}
          </div>
        )}
      </Section>

      <Section title="Related ideas" eyebrow="Ideas" stagger={4}>
        {data.related_ideas.length === 0 ? (
          <StateScreen title="Sin ideas relacionadas" body="No hay ideas triadas a este proyecto." />
        ) : (
          <div className="stack-list">
            {data.related_ideas.map((item, index) => (
              <article className="list-card reveal" key={item.id} style={{ "--stagger": index } as React.CSSProperties}>
                <div className="row spread">
                  <div>
                    <h4>{item.source}</h4>
                    <p>{item.raw_text}</p>
                  </div>
                  <StatusChip value={item.status} />
                </div>
                <div className="cell-subtitle">{formatDateTime(item.created_at)}</div>
              </article>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function ProjectRuns({ data }: { data: ProjectDetailResponse }) {
  return (
    <Section title="Recent runs" eyebrow="Top 5" stagger={1}>
      {data.recent_runs.length === 0 ? (
        <StateScreen title="Sin runs" body="Este proyecto todavía no registra corridas recientes." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>started</th>
                <th>agent</th>
                <th>mode</th>
                <th>status</th>
                <th>summary</th>
                <th>files</th>
                <th>trace</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_runs.map((run, index) => (
                <tr key={run.id} className="reveal" style={{ "--stagger": index } as React.CSSProperties}>
                  <td>{formatDateTime(run.started_at)}</td>
                  <td>{run.agent}</td>
                  <td>{run.mode || "—"}</td>
                  <td>
                    <StatusChip value={run.status} live={isLiveStatus(run.status)} />
                  </td>
                  <td>{run.summary || "—"}</td>
                  <td>{run.files_touched ?? "—"}</td>
                  <td>{run.langfuse_trace_id || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function ProjectHandoffs({ data }: { data: ProjectDetailResponse }) {
  return (
    <Section title="Open handoffs" eyebrow="Read-only" stagger={1}>
      {data.open_handoffs.length === 0 ? (
        <StateScreen title="Sin handoffs abiertos" body="La bandeja de coordinación del proyecto está limpia." />
      ) : (
        <div className="stack-list">
          {data.open_handoffs.map((handoff, index) => (
            <article className="list-card reveal" key={handoff.id} style={{ "--stagger": index } as React.CSSProperties}>
              <div className="row spread">
                <div>
                  <h4>
                    {handoff.from_actor} → {handoff.to_actor}
                  </h4>
                  <p>{handoff.message || "Sin mensaje."}</p>
                </div>
                <StatusChip value={handoff.status} />
              </div>
              <KeyValueList
                items={[
                  { label: "reason", value: sentenceCase(handoff.reason) },
                  { label: "created", value: formatDateTime(handoff.created_at) },
                ]}
              />
            </article>
          ))}
        </div>
      )}
    </Section>
  );
}

function ProjectDecisions({ data }: { data: ProjectDetailResponse }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState({
    title: "",
    context: "",
    decision: "",
    consequences: "",
    status: "active" as "proposed" | "active",
  });
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [supersedeTargetId, setSupersedeTargetId] = useState<string | null>(null);
  const [supersedeDraft, setSupersedeDraft] = useState({
    title: "",
    context: "",
    decision: "",
    consequences: "",
    status: "active" as "proposed" | "active",
  });
  const createDecisionMutation = useMutation({
    mutationFn: () =>
      createDecision({
        project_id: data.project.id,
        title: draft.title,
        context: draft.context,
        decision: draft.decision,
        consequences: draft.consequences || null,
        status: draft.status,
        created_by: "dashboard-ui",
      }),
    onSuccess: async (created: DecisionRecord) => {
      setDecisionError(null);
      setDecisionMessage(`Decision created: ${created.title}.`);
      setDraft({
        title: "",
        context: "",
        decision: "",
        consequences: "",
        status: "active",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-detail", data.project.id] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-graph", data.project.id] }),
      ]);
    },
    onError: (error: Error) => {
      setDecisionMessage(null);
      setDecisionError(error.message);
    },
  });
  const supersedeDecisionMutation = useMutation({
    mutationFn: () => {
      if (!supersedeTargetId) {
        throw new Error("Missing decision to supersede");
      }
      return supersedeDecision(supersedeTargetId, {
        title: supersedeDraft.title,
        context: supersedeDraft.context,
        decision: supersedeDraft.decision,
        consequences: supersedeDraft.consequences || null,
        status: supersedeDraft.status,
        created_by: "dashboard-ui",
      });
    },
    onSuccess: async (created: DecisionRecord) => {
      setDecisionError(null);
      setDecisionMessage(`Decision superseded with: ${created.title}.`);
      setSupersedeTargetId(null);
      setSupersedeDraft({
        title: "",
        context: "",
        decision: "",
        consequences: "",
        status: "active",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-detail", data.project.id] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-graph", data.project.id] }),
      ]);
    },
    onError: (error: Error) => {
      setDecisionMessage(null);
      setDecisionError(error.message);
    },
  });

  async function handleCreateDecision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDecisionMessage(null);
    setDecisionError(null);
    await createDecisionMutation.mutateAsync();
  }

  function startSupersede(decision: ProjectDetailResponse["decisions"][number]) {
    setDecisionMessage(null);
    setDecisionError(null);
    setSupersedeTargetId(decision.id);
    setSupersedeDraft({
      title: decision.title,
      context: decision.context || "",
      decision: "",
      consequences: "",
      status: "active",
    });
  }

  async function handleSupersedeDecision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supersedeTargetId) {
      return;
    }
    if (!window.confirm("Create a replacement decision and mark the current one as superseded?")) {
      return;
    }
    setDecisionMessage(null);
    setDecisionError(null);
    await supersedeDecisionMutation.mutateAsync();
  }

  return (
    <Section title="Recent decisions" eyebrow="Top 5" stagger={1}>
      <div className="stack-list">
        <form className="task-form list-card" onSubmit={handleCreateDecision}>
          <div className="eyebrow">Create decision</div>
          <div className="inline-form-grid">
            <input
              value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder="Decision title"
            />
            <select
              value={draft.status}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  status: event.target.value as "proposed" | "active",
                }))
              }
            >
              <option value="active">active</option>
              <option value="proposed">proposed</option>
            </select>
          </div>
          <input
            value={draft.context}
            onChange={(event) => setDraft((current) => ({ ...current, context: event.target.value }))}
            placeholder="Context"
          />
          <textarea
            value={draft.decision}
            onChange={(event) => setDraft((current) => ({ ...current, decision: event.target.value }))}
            placeholder="Decision"
            rows={4}
          />
          <textarea
            value={draft.consequences}
            onChange={(event) => setDraft((current) => ({ ...current, consequences: event.target.value }))}
            placeholder="Consequences"
            rows={3}
          />
          <div className="task-actions">
            <button className="primary-button" disabled={createDecisionMutation.isPending} type="submit">
              {createDecisionMutation.isPending ? "Creating..." : "Create decision"}
            </button>
          </div>
          {decisionMessage ? <p className="form-success">{decisionMessage}</p> : null}
          {decisionError ? <p className="form-error">{decisionError}</p> : null}
        </form>

        {data.decisions.length === 0 ? (
          <StateScreen title="Sin decisiones" body="Este proyecto todavia no tiene decisiones persistidas." />
        ) : (
          data.decisions.map((decision, index) => (
            <article className="list-card reveal" key={decision.id} style={{ "--stagger": index } as React.CSSProperties}>
              <div className="row spread">
                <h4>{decision.title}</h4>
                <StatusChip value={decision.status} />
              </div>
              <p>{decision.decision}</p>
              <KeyValueList
                items={[
                  { label: "context", value: decision.context || "-" },
                  { label: "consequences", value: decision.consequences || "-" },
                  { label: "created by", value: decision.created_by || "-" },
                  { label: "supersedes", value: decision.supersedes || "-" },
                  { label: "created", value: formatDateTime(decision.created_at) },
                ]}
              />
              {decision.status !== "superseded" ? (
                <div className="task-actions">
                  <button className="secondary-button" onClick={() => startSupersede(decision)} type="button">
                    {supersedeTargetId === decision.id ? "Superseding..." : "Supersede"}
                  </button>
                </div>
              ) : null}
              {supersedeTargetId === decision.id ? (
                <form className="task-form nested-list-card" onSubmit={handleSupersedeDecision}>
                  <div className="eyebrow">Supersede decision</div>
                  <input
                    value={supersedeDraft.title}
                    onChange={(event) => setSupersedeDraft((current) => ({ ...current, title: event.target.value }))}
                    placeholder="Replacement title"
                  />
                  <select
                    value={supersedeDraft.status}
                    onChange={(event) =>
                      setSupersedeDraft((current) => ({
                        ...current,
                        status: event.target.value as "proposed" | "active",
                      }))
                    }
                  >
                    <option value="active">active</option>
                    <option value="proposed">proposed</option>
                  </select>
                  <textarea
                    rows={3}
                    value={supersedeDraft.context}
                    onChange={(event) => setSupersedeDraft((current) => ({ ...current, context: event.target.value }))}
                    placeholder="Why does this supersede the previous decision?"
                  />
                  <textarea
                    rows={4}
                    value={supersedeDraft.decision}
                    onChange={(event) => setSupersedeDraft((current) => ({ ...current, decision: event.target.value }))}
                    placeholder="Replacement decision"
                  />
                  <textarea
                    rows={3}
                    value={supersedeDraft.consequences}
                    onChange={(event) =>
                      setSupersedeDraft((current) => ({ ...current, consequences: event.target.value }))
                    }
                    placeholder="Consequences"
                  />
                  <div className="task-actions">
                    <button className="primary-button" disabled={supersedeDecisionMutation.isPending} type="submit">
                      {supersedeDecisionMutation.isPending ? "Superseding..." : "Confirm supersede"}
                    </button>
                    <button className="secondary-button" onClick={() => setSupersedeTargetId(null)} type="button">
                      Cancel
                    </button>
                  </div>
                </form>
              ) : null}
            </article>
          ))
        )}
      </div>
    </Section>
  );
}

function ProjectAudit({ data }: { data: ProjectDetailResponse }) {
  return (
    <Section title="Latest audit" eyebrow="Read-only" stagger={1}>
      {data.latest_audit === null ? (
        <StateScreen title="Sin audit cargado" body="El último reporte todavía no existe para este proyecto." />
      ) : (
        <div className="audit-layout">
          <div className="stack-list compact">
            <StatusChip value={data.latest_audit.verdict} />
            <h4>{data.latest_audit.summary || "Sin summary"}</h4>
            <KeyValueList
              items={[
                {
                  label: "confidence",
                  value:
                    data.latest_audit.confidence === null ? "—" : `${Math.round(data.latest_audit.confidence * 100)}%`,
                },
                { label: "created", value: formatDateTime(data.latest_audit.created_at) },
              ]}
            />
          </div>
          <div className="stack-list">
            <div className="eyebrow">Findings</div>
            {data.latest_audit.findings.length === 0 ? (
              <p className="muted-copy">No hay findings persistidos para este audit.</p>
            ) : (
              data.latest_audit.findings.map((finding, index) => (
                <article className="list-card reveal" key={index} style={{ "--stagger": index } as React.CSSProperties}>
                  <pre>{JSON.stringify(finding, null, 2)}</pre>
                </article>
              ))
            )}
          </div>
        </div>
      )}
    </Section>
  );
}

function ResearchPage() {
  const query = useQuery({
    queryKey: ["dashboard-research"],
    queryFn: getResearchOverview,
  });

  if (query.isLoading) {
    return (
      <AppShell title="Research" subtitle="Candidates, ready-to-promote, queue y reportes recientes con acciones seguras ya habilitadas.">
        <div className="kpi-grid research-kpis">
          {Array.from({ length: 3 }).map((_, index) => (
            <SkeletonBlock key={index} height={130} />
          ))}
        </div>
        <SkeletonBlock height={480} />
      </AppShell>
    );
  }

  if (query.isError) {
    return (
      <AppShell title="Research" subtitle="Candidates, ready-to-promote, queue y reportes recientes con acciones seguras ya habilitadas.">
        <StateScreen title="No pude cargar research" body={query.error.message} tone="bad" />
      </AppShell>
    );
  }

  const data = query.data as ResearchOverviewResponse;

  return (
    <AppShell title="Research" subtitle="Candidates, ready-to-promote, queue y reportes recientes con acciones seguras ya habilitadas.">
      <div className="kpi-grid research-kpis">
        <KpiCard label="Ready to promote" value={data.kpis.ready_to_promote} note="flag real del backend" stagger={0} />
        <KpiCard label="Queue due today" value={data.kpis.queue_due_today} note="pending hasta end of today" stagger={1} />
        <KpiCard label="Pending queue total" value={data.kpis.pending_queue_total} note="backlog actual de research" stagger={2} />
      </div>

      <Section
        title="Ready to promote"
        eyebrow="Read-only shortlist"
        stagger={3}
        aside={<span className="meta-pill">sin acción de promote en V1B</span>}
      >
        {data.ready_to_promote.length === 0 ? (
          <StateScreen title="Nada listo para promover" body="La shortlist todavía no tiene candidatas marcadas como listas." />
        ) : (
          <div className="stack-list">
            {data.ready_to_promote.map((item, index) => (
              <article className="list-card reveal" key={item.id} style={{ "--stagger": index } as React.CSSProperties}>
                <div className="row spread">
                  <div>
                    <h4>{item.name}</h4>
                    <p>{item.slug}</p>
                  </div>
                  <StatusChip value={item.status} />
                </div>
                <KeyValueList
                  items={[
                    { label: "last verdict", value: item.last_research?.verdict || "—" },
                    { label: "confidence", value: item.last_research?.confidence === null || item.last_research?.confidence === undefined ? "—" : `${Math.round(item.last_research.confidence * 100)}%` },
                    { label: "updated", value: formatDateTime(item.last_research?.created_at || null) },
                  ]}
                />
              </article>
            ))}
          </div>
        )}
      </Section>

      <div className="dashboard-grid">
        <Section title="Candidates" eyebrow="Full table" stagger={4}>
          {data.candidates.length === 0 ? (
            <StateScreen title="Sin candidates" body="La base actual no tiene candidatas registradas." />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>candidate</th>
                    <th>category</th>
                    <th>status</th>
                    <th>priority</th>
                    <th>importance</th>
                    <th>size</th>
                    <th>last research</th>
                    <th>promoted to</th>
                  </tr>
                </thead>
                <tbody>
                  {data.candidates.map((candidate, index) => (
                    <tr key={candidate.id} className="reveal" style={{ "--stagger": index } as React.CSSProperties}>
                      <td>
                        <div className="cell-title">{candidate.name}</div>
                        <div className="cell-subtitle">{candidate.slug}</div>
                      </td>
                      <td>{candidate.category || "—"}</td>
                      <td>
                        <StatusChip value={candidate.status} />
                      </td>
                      <td>{candidate.priority ?? "—"}</td>
                      <td>{candidate.importance ?? "—"}</td>
                      <td>{candidate.estimated_size ?? "—"}</td>
                      <td>{candidate.last_research ? formatDate(candidate.last_research.created_at) : "—"}</td>
                      <td>{candidate.promoted_to_project_id || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="Queue" eyebrow="Pending + history" stagger={5}>
          {data.queue.length === 0 ? (
            <StateScreen title="Queue vacía" body="No hay items en la cola de research." />
          ) : (
            <div className="stack-list">
              {data.queue.map((item, index) => (
                <article className="list-card reveal" key={item.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <h4>{item.queue_type}</h4>
                      <p>{item.candidate_id || item.project_id || "Sin referencia"}</p>
                    </div>
                    <StatusChip value={item.status} live={isLiveStatus(item.status)} />
                  </div>
                  <KeyValueList
                    items={[
                      { label: "priority", value: item.priority ?? "—" },
                      { label: "scheduled", value: item.scheduled_for },
                      { label: "last run", value: formatDateTime(item.last_run_at) },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Recent reports" eyebrow="Latest" stagger={6}>
          {data.recent_reports.length === 0 ? (
            <StateScreen title="Sin reports" body="Todavía no hay reportes recientes para mostrar." />
          ) : (
            <div className="stack-list">
              {data.recent_reports.map((report, index) => (
                <article className="list-card reveal" key={report.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <h4>{report.candidate_id}</h4>
                      <p>{report.summary || "Sin summary."}</p>
                    </div>
                    <StatusChip value={report.verdict} />
                  </div>
                  <KeyValueList
                    items={[
                      { label: "confidence", value: report.confidence === null ? "—" : `${Math.round(report.confidence * 100)}%` },
                      { label: "created", value: formatDateTime(report.created_at) },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>
    </AppShell>
  );
}

function ResearchPageF4B() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["dashboard-research"],
    queryFn: getResearchOverview,
  });
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [selectedQueueId, setSelectedQueueId] = useState<string | null>(null);
  const [candidateActionMessage, setCandidateActionMessage] = useState<string | null>(null);
  const [candidateActionError, setCandidateActionError] = useState<string | null>(null);
  const [candidateEditMessage, setCandidateEditMessage] = useState<string | null>(null);
  const [candidateEditError, setCandidateEditError] = useState<string | null>(null);
  const [queueActionMessage, setQueueActionMessage] = useState<string | null>(null);
  const [queueActionError, setQueueActionError] = useState<string | null>(null);
  const [promoteDraft, setPromoteDraft] = useState({
    project_id: "",
    name: "",
    host_machine: "",
    kind: "project" as "core" | "project" | "vertical" | "group",
  });
  const [queueDraft, setQueueDraft] = useState({
    scheduled_for: "",
    notes: "",
  });
  const [candidateEditDraft, setCandidateEditDraft] = useState<CandidatePatchInput>({
    status: "proposed",
    priority: null,
    importance: null,
    estimated_size: null,
    hypothesis: "",
    problem_desc: "",
  });

  const data = query.data as ResearchOverviewResponse | undefined;
  const readyCandidateIds = new Set((data?.ready_to_promote || []).map((item) => item.id));
  const candidatesById = new Map((data?.candidates || []).map((candidate) => [candidate.id, candidate]));
  const activeCandidate =
    data?.candidates.find((candidate) => candidate.id === selectedCandidateId) ||
    data?.candidates.find((candidate) => readyCandidateIds.has(candidate.id)) ||
    data?.candidates[0] ||
    null;
  const activeQueue = data?.queue.find((item) => item.id === selectedQueueId) || data?.queue[0] || null;
  const activeCandidateReady = Boolean(activeCandidate && readyCandidateIds.has(activeCandidate.id));
  const activeCandidatePromoted = Boolean(activeCandidate?.promoted_to_project_id || activeCandidate?.status === "promoted");

  const runCandidateMutation = useMutation({
    mutationFn: (candidateId: string) => runDashboardAgent({ target_type: "candidate", target_id: candidateId }),
    onSuccess: async (payload: AgentRunResponse) => {
      setCandidateActionError(null);
      setCandidateActionMessage(payload.summary || "Candidate run completed.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-research"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-runs"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
      ]);
    },
    onError: (error: Error) => {
      setCandidateActionMessage(null);
      setCandidateActionError(error.message);
    },
  });

  const promoteCandidateMutation = useMutation({
    mutationFn: ({
      candidateId,
      payload,
    }: {
      candidateId: string;
      payload: {
        project_id: string;
        name?: string | null;
        host_machine?: string | null;
        kind?: "core" | "project" | "vertical" | "group";
      };
    }) => promoteCandidate(candidateId, payload),
    onSuccess: async (payload: CandidatePromotionResponse) => {
      setCandidateActionError(null);
      setCandidateActionMessage(payload.message);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-research"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-projects"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
      ]);
    },
    onError: (error: Error) => {
      setCandidateActionMessage(null);
      setCandidateActionError(error.message);
    },
  });

  const updateCandidateMutation = useMutation({
    mutationFn: ({ candidateId, payload }: { candidateId: string; payload: CandidatePatchInput }) =>
      updateCandidate(candidateId, payload),
    onSuccess: async () => {
      setCandidateEditError(null);
      setCandidateEditMessage("Candidate metadata updated.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-research"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
      ]);
    },
    onError: (error: Error) => {
      setCandidateEditMessage(null);
      setCandidateEditError(error.message);
    },
  });

  const requeueMutation = useMutation({
    mutationFn: (payload: { queue_id: string; scheduled_for?: string | null; notes?: string | null }) =>
      requeueResearchQueue(payload),
    onSuccess: async (payload: ResearchQueueItem) => {
      setQueueActionError(null);
      setQueueActionMessage(`Queue item ${payload.id} requeued.`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-research"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
      ]);
    },
    onError: (error: Error) => {
      setQueueActionMessage(null);
      setQueueActionError(error.message);
    },
  });

  useEffect(() => {
    if (!activeCandidate) {
      return;
    }
    setPromoteDraft({
      project_id: activeCandidate.slug,
      name: activeCandidate.name,
      host_machine: "",
      kind: "project",
    });
  }, [activeCandidate?.id, activeCandidate?.slug, activeCandidate?.name]);

  useEffect(() => {
    if (!activeCandidate) {
      return;
    }
    setCandidateEditDraft({
      status: activeCandidate.status as CandidatePatchInput["status"],
      priority: activeCandidate.priority,
      importance: activeCandidate.importance,
      estimated_size: activeCandidate.estimated_size,
      hypothesis: activeCandidate.hypothesis,
      problem_desc: activeCandidate.problem_desc || "",
    });
  }, [
    activeCandidate?.id,
    activeCandidate?.status,
    activeCandidate?.priority,
    activeCandidate?.importance,
    activeCandidate?.estimated_size,
    activeCandidate?.hypothesis,
    activeCandidate?.problem_desc,
  ]);

  useEffect(() => {
    if (!activeQueue) {
      return;
    }
    setQueueDraft({
      scheduled_for: formatDateInput(activeQueue.scheduled_for),
      notes: activeQueue.notes || "",
    });
  }, [activeQueue?.id, activeQueue?.scheduled_for, activeQueue?.notes]);

  if (query.isLoading) {
    return (
      <AppShell title="Research" subtitle="Candidates, ready-to-promote, queue y reportes recientes con acciones seguras para run-agent, requeue y promote.">
        <div className="kpi-grid research-kpis">
          {Array.from({ length: 3 }).map((_, index) => (
            <SkeletonBlock key={index} height={130} />
          ))}
        </div>
        <SkeletonBlock height={480} />
      </AppShell>
    );
  }

  if (query.isError || !data) {
    return (
      <AppShell title="Research" subtitle="Candidates, ready-to-promote, queue y reportes recientes con acciones seguras para run-agent, requeue y promote.">
        <StateScreen title="No pude cargar research" body={query.isError ? query.error.message : "Research data missing"} tone="bad" />
      </AppShell>
    );
  }

  async function handleRunCandidate() {
    if (!activeCandidate) {
      return;
    }
    if (!window.confirm(`Run agent now for candidate ${activeCandidate.name}?`)) {
      return;
    }
    setCandidateActionMessage(null);
    setCandidateActionError(null);
    await runCandidateMutation.mutateAsync(activeCandidate.id);
  }

  async function handlePromoteCandidate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCandidate) {
      return;
    }
    if (!promoteDraft.project_id.trim()) {
      setCandidateActionMessage(null);
      setCandidateActionError("project_id is required to promote a candidate.");
      return;
    }
    if (!window.confirm(`Promote candidate ${activeCandidate.name} into project ${promoteDraft.project_id.trim()}?`)) {
      return;
    }
    setCandidateActionMessage(null);
    setCandidateActionError(null);
    await promoteCandidateMutation.mutateAsync({
      candidateId: activeCandidate.id,
      payload: {
        project_id: promoteDraft.project_id.trim(),
        name: promoteDraft.name.trim() || null,
        host_machine: promoteDraft.host_machine.trim() || null,
        kind: promoteDraft.kind,
      },
    });
  }

  async function handleSaveCandidateMetadata(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCandidate) {
      return;
    }
    setCandidateEditMessage(null);
    setCandidateEditError(null);
    await updateCandidateMutation.mutateAsync({
      candidateId: activeCandidate.id,
      payload: {
        status: candidateEditDraft.status,
        priority: candidateEditDraft.priority ?? null,
        importance: candidateEditDraft.importance ?? null,
        estimated_size: candidateEditDraft.estimated_size ?? null,
        hypothesis: candidateEditDraft.hypothesis?.trim() || null,
        problem_desc: candidateEditDraft.problem_desc?.trim() || null,
      },
    });
  }

  async function handleRequeue(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeQueue) {
      return;
    }
    setQueueActionMessage(null);
    setQueueActionError(null);
    await requeueMutation.mutateAsync({
      queue_id: activeQueue.id,
      scheduled_for: queueDraft.scheduled_for ? `${queueDraft.scheduled_for}T09:00:00Z` : null,
      notes: queueDraft.notes.trim() || null,
    });
  }

  return (
    <AppShell title="Research" subtitle="Candidates, ready-to-promote, queue y reportes recientes con acciones seguras para run-agent, requeue y promote.">
      <div className="kpi-grid research-kpis">
        <KpiCard label="Ready to promote" value={data.kpis.ready_to_promote} note="flag real del backend" stagger={0} />
        <KpiCard label="Queue due today" value={data.kpis.queue_due_today} note="pending hasta end of today" stagger={1} />
        <KpiCard label="Pending queue total" value={data.kpis.pending_queue_total} note="backlog actual de research" stagger={2} />
      </div>

      <Section title="Ready to promote" eyebrow="Safe actions" stagger={3} aside={<span className="meta-pill">run-agent + promote</span>}>
        {data.ready_to_promote.length === 0 ? (
          <StateScreen title="Nada listo para promover" body="La shortlist todavia no tiene candidatas marcadas como listas." />
        ) : (
          <div className="stack-list">
            {data.ready_to_promote.map((item, index) => (
              <article className="list-card reveal" key={item.id} style={{ "--stagger": index } as React.CSSProperties}>
                <div className="row spread">
                  <div>
                    <h4>{item.name}</h4>
                    <p>{item.slug}</p>
                  </div>
                  <StatusChip value={item.status} />
                </div>
                <KeyValueList
                  items={[
                    { label: "last verdict", value: item.last_research?.verdict || "-" },
                    {
                      label: "confidence",
                      value:
                        item.last_research?.confidence === null || item.last_research?.confidence === undefined
                          ? "-"
                          : `${Math.round(item.last_research.confidence * 100)}%`,
                    },
                    { label: "updated", value: formatDateTime(item.last_research?.created_at || null) },
                  ]}
                />
                <div className="task-actions">
                  <button className="secondary-button" onClick={() => setSelectedCandidateId(item.id)} type="button">
                    Focus candidate
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Section>

      <div className="dashboard-grid">
        <Section title="Candidates" eyebrow="Full table" stagger={4}>
          {data.candidates.length === 0 ? (
            <StateScreen title="Sin candidates" body="La base actual no tiene candidatas registradas." />
          ) : (
            <div className="detail-layout">
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>candidate</th>
                      <th>category</th>
                      <th>status</th>
                      <th>priority</th>
                      <th>importance</th>
                      <th>size</th>
                      <th>last research</th>
                      <th>promoted to</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.candidates.map((candidate, index) => (
                      <tr
                        key={candidate.id}
                        className={`reveal ${activeCandidate?.id === candidate.id ? "selected-row" : ""}`}
                        style={{ "--stagger": index } as React.CSSProperties}
                        onClick={() => setSelectedCandidateId(candidate.id)}
                      >
                        <td>
                          <div className="cell-title">{candidate.name}</div>
                          <div className="cell-subtitle">{candidate.slug}</div>
                        </td>
                        <td>{candidate.category || "-"}</td>
                        <td>
                          <StatusChip value={candidate.status} />
                        </td>
                        <td>{candidate.priority ?? "-"}</td>
                        <td>{candidate.importance ?? "-"}</td>
                        <td>{candidate.estimated_size ?? "-"}</td>
                        <td>{candidate.last_research ? formatDate(candidate.last_research.created_at) : "-"}</td>
                        <td>{candidate.promoted_to_project_id || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="detail-panel">
                <Section title="Candidate actions" eyebrow="Safe writes" stagger={0}>
                  {!activeCandidate ? (
                    <StateScreen title="Sin candidate seleccionado" body="Elegi una candidata para correr research o promoverla." />
                  ) : (
                    <div className="stack-list">
                      <article className="list-card">
                        <div className="row spread">
                          <div>
                            <h4>{activeCandidate.name}</h4>
                            <p>{activeCandidate.slug}</p>
                          </div>
                          <StatusChip value={activeCandidate.status} />
                        </div>
                        <KeyValueList
                          items={[
                            { label: "category", value: activeCandidate.category || "-" },
                            { label: "parent group", value: activeCandidate.parent_group || "-" },
                            { label: "priority", value: activeCandidate.priority ?? "-" },
                            { label: "importance", value: activeCandidate.importance ?? "-" },
                            { label: "size", value: activeCandidate.estimated_size ?? "-" },
                            { label: "ready to promote", value: activeCandidateReady ? "yes" : "no" },
                            { label: "hypothesis", value: activeCandidate.hypothesis || "-" },
                            { label: "problem", value: activeCandidate.problem_desc || "-" },
                            {
                              label: "last research",
                              value: activeCandidate.last_research ? formatDateTime(activeCandidate.last_research.created_at) : "-",
                            },
                          ]}
                        />
                        <div className="task-actions">
                          <button
                            className="primary-button"
                            disabled={runCandidateMutation.isPending}
                            onClick={handleRunCandidate}
                            type="button"
                          >
                            {runCandidateMutation.isPending ? "Running..." : "Run agent"}
                          </button>
                        </div>
                        {candidateActionMessage ? <p className="form-success">{candidateActionMessage}</p> : null}
                        {candidateActionError ? <p className="form-error">{candidateActionError}</p> : null}
                      </article>

                      <form className="task-form list-card" onSubmit={handleSaveCandidateMetadata}>
                        <div className="eyebrow">Edit candidate metadata</div>
                        <div className="inline-form-grid">
                          <select
                            value={candidateEditDraft.status || ""}
                            onChange={(event) =>
                              setCandidateEditDraft((current) => ({
                                ...current,
                                status: event.target.value as CandidatePatchInput["status"],
                              }))
                            }
                          >
                            <option value="proposed">proposed</option>
                            <option value="investigating">investigating</option>
                            <option value="promising">promising</option>
                            <option value="paused">paused</option>
                            <option value="killed">killed</option>
                            <option value="promoted">promoted</option>
                          </select>
                          <input
                            type="number"
                            min={1}
                            max={4}
                            value={candidateEditDraft.estimated_size ?? ""}
                            onChange={(event) =>
                              setCandidateEditDraft((current) => ({
                                ...current,
                                estimated_size: event.target.value ? Number(event.target.value) : null,
                              }))
                            }
                            placeholder="estimated_size"
                          />
                        </div>
                        <div className="inline-form-grid">
                          <input
                            type="number"
                            min={1}
                            max={6}
                            value={candidateEditDraft.priority ?? ""}
                            onChange={(event) =>
                              setCandidateEditDraft((current) => ({
                                ...current,
                                priority: event.target.value ? Number(event.target.value) : null,
                              }))
                            }
                            placeholder="priority"
                          />
                          <input
                            type="number"
                            min={1}
                            max={5}
                            value={candidateEditDraft.importance ?? ""}
                            onChange={(event) =>
                              setCandidateEditDraft((current) => ({
                                ...current,
                                importance: event.target.value ? Number(event.target.value) : null,
                              }))
                            }
                            placeholder="importance"
                          />
                        </div>
                        <textarea
                          rows={3}
                          value={candidateEditDraft.hypothesis || ""}
                          onChange={(event) =>
                            setCandidateEditDraft((current) => ({ ...current, hypothesis: event.target.value }))
                          }
                          placeholder="Hypothesis"
                        />
                        <textarea
                          rows={3}
                          value={candidateEditDraft.problem_desc || ""}
                          onChange={(event) =>
                            setCandidateEditDraft((current) => ({ ...current, problem_desc: event.target.value }))
                          }
                          placeholder="Problem description"
                        />
                        <p className="panel-note">
                          `kill_verdict` sigue fuera de esta UI porque en el modelo real es JSON y no tiene una
                          semántica mínima suficientemente estable para exponerlo como formulario chico en F5A.
                        </p>
                        <div className="task-actions">
                          <button className="primary-button" disabled={updateCandidateMutation.isPending} type="submit">
                            {updateCandidateMutation.isPending ? "Saving..." : "Save candidate metadata"}
                          </button>
                        </div>
                        {candidateEditMessage ? <p className="form-success">{candidateEditMessage}</p> : null}
                        {candidateEditError ? <p className="form-error">{candidateEditError}</p> : null}
                      </form>

                      <form className="task-form list-card" onSubmit={handlePromoteCandidate}>
                        <div className="eyebrow">Promote candidate</div>
                        <input
                          value={promoteDraft.project_id}
                          onChange={(event) => setPromoteDraft((current) => ({ ...current, project_id: event.target.value }))}
                          placeholder="project_id"
                        />
                        <div className="inline-form-grid">
                          <input
                            value={promoteDraft.name}
                            onChange={(event) => setPromoteDraft((current) => ({ ...current, name: event.target.value }))}
                            placeholder="Project name"
                          />
                          <input
                            value={promoteDraft.host_machine}
                            onChange={(event) =>
                              setPromoteDraft((current) => ({ ...current, host_machine: event.target.value }))
                            }
                            placeholder="host_machine"
                          />
                        </div>
                        <select
                          value={promoteDraft.kind}
                          onChange={(event) =>
                            setPromoteDraft((current) => ({
                              ...current,
                              kind: event.target.value as "core" | "project" | "vertical" | "group",
                            }))
                          }
                        >
                          <option value="project">project</option>
                          <option value="vertical">vertical</option>
                          <option value="group">group</option>
                          <option value="core">core</option>
                        </select>
                        <p className="panel-note">
                          {activeCandidatePromoted
                            ? `This candidate is already promoted to ${activeCandidate.promoted_to_project_id}.`
                            : activeCandidateReady
                              ? "Promotion uses the existing backend flow and creates the project only after explicit confirmation."
                              : "Promotion stays disabled until the backend marks this candidate as ready to promote."}
                        </p>
                        <div className="task-actions">
                          <button
                            className="primary-button"
                            disabled={promoteCandidateMutation.isPending || !activeCandidateReady || activeCandidatePromoted}
                            type="submit"
                          >
                            {promoteCandidateMutation.isPending ? "Promoting..." : "Promote candidate"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}
                </Section>
              </div>
            </div>
          )}
        </Section>

        <Section title="Queue" eyebrow="Pending + history" stagger={5}>
          {data.queue.length === 0 ? (
            <StateScreen title="Queue vacia" body="No hay items en la cola de research." />
          ) : (
            <div className="detail-layout">
              <div className="stack-list">
                {data.queue.map((item, index) => (
                  <article
                    className={`list-card reveal ${activeQueue?.id === item.id ? "selected-card" : ""}`}
                    key={item.id}
                    onClick={() => setSelectedQueueId(item.id)}
                    style={{ "--stagger": index } as React.CSSProperties}
                  >
                    <div className="row spread">
                      <div>
                        <h4>{item.queue_type}</h4>
                        <p>
                          {item.candidate_id
                            ? candidatesById.get(item.candidate_id)?.name || item.candidate_id
                            : item.project_id || "Sin referencia"}
                        </p>
                      </div>
                      <StatusChip value={item.status} />
                    </div>
                    <KeyValueList
                      items={[
                        { label: "priority", value: item.priority ?? "-" },
                        { label: "scheduled", value: item.scheduled_for },
                        { label: "last run", value: formatDateTime(item.last_run_at) },
                      ]}
                    />
                    {item.notes ? <p className="rich-copy">{item.notes}</p> : null}
                  </article>
                ))}
              </div>

              <div className="detail-panel">
                <Section title="Requeue" eyebrow="Safe action" stagger={0}>
                  {!activeQueue ? (
                    <StateScreen title="Sin queue item seleccionado" body="Elegi un item para reprogramarlo o devolverlo a pending." />
                  ) : (
                    <div className="stack-list">
                      <article className="list-card">
                        <div className="row spread">
                          <div>
                            <h4>{activeQueue.queue_type}</h4>
                            <p>
                              {activeQueue.candidate_id
                                ? candidatesById.get(activeQueue.candidate_id)?.name || activeQueue.candidate_id
                                : activeQueue.project_id || "Sin referencia"}
                            </p>
                          </div>
                          <StatusChip value={activeQueue.status} />
                        </div>
                        <KeyValueList
                          items={[
                            { label: "scheduled", value: activeQueue.scheduled_for },
                            { label: "last run", value: formatDateTime(activeQueue.last_run_at) },
                            { label: "priority", value: activeQueue.priority ?? "-" },
                          ]}
                        />
                      </article>

                      <form className="task-form list-card" onSubmit={handleRequeue}>
                        <div className="eyebrow">Requeue item</div>
                        <input
                          type="date"
                          value={queueDraft.scheduled_for}
                          onChange={(event) =>
                            setQueueDraft((current) => ({ ...current, scheduled_for: event.target.value }))
                          }
                        />
                        <textarea
                          rows={4}
                          value={queueDraft.notes}
                          onChange={(event) => setQueueDraft((current) => ({ ...current, notes: event.target.value }))}
                          placeholder="Optional notes for the requeue"
                        />
                        <div className="task-actions">
                          <button className="primary-button" disabled={requeueMutation.isPending} type="submit">
                            {requeueMutation.isPending ? "Requeueing..." : "Requeue"}
                          </button>
                        </div>
                        {queueActionMessage ? <p className="form-success">{queueActionMessage}</p> : null}
                        {queueActionError ? <p className="form-error">{queueActionError}</p> : null}
                      </form>
                    </div>
                  )}
                </Section>
              </div>
            </div>
          )}
        </Section>

        <Section title="Recent reports" eyebrow="Latest" stagger={6}>
          {data.recent_reports.length === 0 ? (
            <StateScreen title="Sin reports" body="Todavia no hay reportes recientes para mostrar." />
          ) : (
            <div className="stack-list">
              {data.recent_reports.map((report, index) => (
                <article className="list-card reveal" key={report.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <h4>{candidatesById.get(report.candidate_id)?.name || report.candidate_id}</h4>
                      <p>{report.summary || "Sin summary."}</p>
                    </div>
                    <StatusChip value={report.verdict} />
                  </div>
                  <KeyValueList
                    items={[
                      { label: "confidence", value: report.confidence === null ? "-" : `${Math.round(report.confidence * 100)}%` },
                      { label: "created", value: formatDateTime(report.created_at) },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>
    </AppShell>
  );
}

function RunDetailPanel({
  run,
  isLoading,
  errorMessage,
}: {
  run: RunDetail | undefined;
  isLoading: boolean;
  errorMessage: string | null;
}) {
  return (
    <Section title="Run detail" eyebrow="Panel" stagger={1}>
      {isLoading ? (
        <div className="stack-list">
          <SkeletonBlock height={96} />
          <SkeletonBlock height={124} />
          <SkeletonBlock height={164} />
        </div>
      ) : errorMessage ? (
        <StateScreen title="No pude cargar el run" body={errorMessage} tone="bad" />
      ) : !run ? (
        <StateScreen title="Sin run seleccionado" body="Elegí un run de la tabla para ver su payload read-only." />
      ) : (
        <div className="stack-list">
          <article className="list-card">
            <div className="row spread">
              <div>
                <h4>{run.project_name || run.project_id}</h4>
                <p>{run.id}</p>
              </div>
              <StatusChip value={run.status} live={isLiveStatus(run.status)} />
            </div>
            <p className="rich-copy">{run.summary || "Sin summary persistido."}</p>
            <KeyValueList
              items={[
                { label: "agent", value: run.agent },
                { label: "mode", value: run.mode || "—" },
                { label: "started", value: formatDateTime(run.started_at) },
                { label: "ended", value: formatDateTime(run.ended_at) },
                { label: "prompt", value: run.prompt_ref || "—" },
                { label: "trace", value: run.langfuse_trace_id || "—" },
                { label: "files touched", value: run.files_touched_count },
                { label: "cost usd", value: formatCurrency(run.cost_usd) },
                { label: "next step", value: run.next_step_proposed || "—" },
                { label: "worktree", value: run.worktree_path || "—" },
              ]}
            />
          </article>

          <article className="list-card">
            <div className="eyebrow">Files touched</div>
            {run.files_touched && run.files_touched.length > 0 ? (
              <div className="pill-cluster">
                {run.files_touched.map((filePath) => (
                  <span className="meta-pill" key={filePath}>
                    {filePath}
                  </span>
                ))}
              </div>
            ) : (
              <p className="muted-copy">El run no persistió la lista completa de archivos.</p>
            )}
          </article>

          <article className="list-card">
            <div className="eyebrow">Diff stats</div>
            <pre className="json-view">{JSON.stringify(run.diff_stats || {}, null, 2)}</pre>
          </article>

          <article className="list-card">
            <div className="eyebrow">Metadata</div>
            <pre className="json-view">{JSON.stringify(run.metadata || {}, null, 2)}</pre>
          </article>
        </div>
      )}
    </Section>
  );
}

function RunsPage() {
  const [filters, setFilters] = useState({
    project_id: "",
    agent: "",
    status: "",
    mode: "",
  });
  const deferredFilters = useDeferredValue(filters);
  const runsQuery = useQuery({
    queryKey: ["dashboard-runs", deferredFilters],
    queryFn: () => getRecentRuns(deferredFilters),
  });
  const rows = runsQuery.data ?? [];
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const activeRunId = selectedRunId && rows.some((row) => row.id === selectedRunId) ? selectedRunId : rows[0]?.id || null;
  const runDetailQuery = useQuery({
    queryKey: ["dashboard-run-detail", activeRunId],
    queryFn: () => getRunDetail(activeRunId as string),
    enabled: Boolean(activeRunId),
  });

  if (runsQuery.isLoading) {
    return (
      <AppShell title="Runs" subtitle="Timeline read-only de actividad reciente, con panel lateral por run.">
        <div className="detail-layout">
          <SkeletonBlock height={540} />
          <SkeletonBlock height={540} />
        </div>
      </AppShell>
    );
  }

  if (runsQuery.isError) {
    return (
      <AppShell title="Runs" subtitle="Timeline read-only de actividad reciente, con panel lateral por run.">
        <StateScreen title="No pude cargar runs" body={runsQuery.error.message} tone="bad" />
      </AppShell>
    );
  }

  return (
    <AppShell title="Runs" subtitle="Timeline read-only de actividad reciente, con panel lateral por run.">
      <Section
        title="Recent runs"
        eyebrow="Read-only timeline"
        aside={<span className="meta-pill">{rows.length} runs</span>}
        stagger={0}
      >
        <div className="filters">
          <input
            value={filters.project_id}
            onChange={(event) => setFilters((current) => ({ ...current, project_id: event.target.value }))}
            placeholder="project_id"
          />
          <input
            value={filters.agent}
            onChange={(event) => setFilters((current) => ({ ...current, agent: event.target.value }))}
            placeholder="agent"
          />
          <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
            <option value="">Todos los status</option>
            <option value="running">running</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </select>
          <select value={filters.mode} onChange={(event) => setFilters((current) => ({ ...current, mode: event.target.value }))}>
            <option value="">Todos los modos</option>
            <option value="implement">implement</option>
            <option value="plan">plan</option>
            <option value="audit">audit</option>
            <option value="investigate">investigate</option>
            <option value="debug">debug</option>
            <option value="refactor">refactor</option>
          </select>
        </div>

        {rows.length === 0 ? (
          <StateScreen title="Sin runs" body="No hay runs para los filtros actuales." />
        ) : (
          <div className="detail-layout">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>project</th>
                    <th>agent</th>
                    <th>mode</th>
                    <th>status</th>
                    <th>started</th>
                    <th>ended</th>
                    <th>summary</th>
                    <th>files</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((run, index) => (
                    <tr
                      key={run.id}
                      className={`reveal ${activeRunId === run.id ? "selected-row" : ""}`}
                      style={{ "--stagger": index } as React.CSSProperties}
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      <td>
                        <div className="cell-title">{run.project_name || run.project_id}</div>
                        <div className="cell-subtitle">{run.id}</div>
                      </td>
                      <td>{run.agent}</td>
                      <td>{run.mode || "—"}</td>
                      <td>
                        <StatusChip value={run.status} live={isLiveStatus(run.status)} />
                      </td>
                      <td>{formatDateTime(run.started_at)}</td>
                      <td>{formatDateTime(run.ended_at)}</td>
                      <td>{truncateText(run.summary || "Sin summary", 88)}</td>
                      <td>{run.files_touched_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="detail-panel">
              <RunDetailPanel
                run={runDetailQuery.data}
                isLoading={runDetailQuery.isLoading}
                errorMessage={runDetailQuery.isError ? runDetailQuery.error.message : null}
              />
            </div>
          </div>
        )}
      </Section>

      <Section title="Notes" eyebrow="Phase 1" stagger={2}>
        <p className="panel-note">
          Esta vista queda deliberadamente read-only. Si un run trae `langfuse_trace_id`, el dashboard lo muestra sin duplicar observabilidad
          ni exponer acciones write.
        </p>
      </Section>
    </AppShell>
  );
}

function HandoffsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({
    to_actor: "",
    project_id: "",
  });
  const [resolutionNote, setResolutionNote] = useState("");
  const [handoffActionMessage, setHandoffActionMessage] = useState<string | null>(null);
  const [handoffActionError, setHandoffActionError] = useState<string | null>(null);
  const deferredFilters = useDeferredValue(filters);
  const handoffsQuery = useQuery({
    queryKey: ["dashboard-handoffs", deferredFilters],
    queryFn: () => getOpenHandoffs(deferredFilters),
  });
  const rows = handoffsQuery.data ?? [];
  const [selectedHandoffId, setSelectedHandoffId] = useState<string | null>(null);
  const activeHandoff = rows.find((handoff) => handoff.id === selectedHandoffId) || rows[0] || null;
  const grouped = rows.reduce<Record<string, HandoffSummary[]>>((accumulator, handoff) => {
    const key = handoff.to_actor || "unassigned";
    accumulator[key] = accumulator[key] || [];
    accumulator[key].push(handoff);
    return accumulator;
  }, {});
  const resolveHandoffMutation = useMutation({
    mutationFn: (payload: { handoff_id: string; resolution_note?: string | null }) => resolveDashboardHandoff(payload),
    onSuccess: async () => {
      setHandoffActionError(null);
      setHandoffActionMessage("Handoff resolved successfully.");
      setResolutionNote("");
      setSelectedHandoffId(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-handoffs"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-projects"] }),
      ]);
    },
    onError: (error: Error) => {
      setHandoffActionMessage(null);
      setHandoffActionError(error.message);
    },
  });

  async function handleResolveHandoff() {
    if (!activeHandoff) {
      return;
    }
    if (!window.confirm(`Resolve handoff ${activeHandoff.id}?`)) {
      return;
    }
    setHandoffActionMessage(null);
    setHandoffActionError(null);
    await resolveHandoffMutation.mutateAsync({
      handoff_id: activeHandoff.id,
      resolution_note: resolutionNote || null,
    });
  }

  if (handoffsQuery.isLoading) {
    return (
      <AppShell title="Handoffs" subtitle="Inbox operativo con resolucion segura agrupado por actor destino.">
        <div className="detail-layout">
          <SkeletonBlock height={520} />
          <SkeletonBlock height={520} />
        </div>
      </AppShell>
    );
  }

  if (handoffsQuery.isError) {
    return (
      <AppShell title="Handoffs" subtitle="Inbox operativo con resolucion segura agrupado por actor destino.">
        <StateScreen title="No pude cargar handoffs" body={handoffsQuery.error.message} tone="bad" />
      </AppShell>
    );
  }

  return (
    <AppShell title="Handoffs" subtitle="Inbox operativo con resolucion segura agrupado por actor destino.">
      <Section
        title="Open handoffs"
        eyebrow="Grouped inbox"
        aside={<span className="meta-pill">{rows.length} abiertos</span>}
        stagger={0}
      >
        <div className="filters handoff-filters">
          <input
            value={filters.to_actor}
            onChange={(event) => setFilters((current) => ({ ...current, to_actor: event.target.value }))}
            placeholder="to_actor"
          />
          <input
            value={filters.project_id}
            onChange={(event) => setFilters((current) => ({ ...current, project_id: event.target.value }))}
            placeholder="project_id"
          />
        </div>
        {handoffActionMessage ? <p className="form-success">{handoffActionMessage}</p> : null}
        {handoffActionError ? <p className="form-error">{handoffActionError}</p> : null}

        {rows.length === 0 ? (
          <StateScreen title="Inbox vacio" body="No hay handoffs abiertos con los filtros actuales." />
        ) : (
          <div className="detail-layout">
            <div className="group-stack">
              {Object.entries(grouped).map(([actor, items], index) => (
                <article className="panel reveal group-block" key={actor} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <div>
                      <div className="eyebrow">to actor</div>
                      <h3 className="group-title">{actor}</h3>
                    </div>
                    <span className="meta-pill">{items.length} open</span>
                  </div>
                  <div className="stack-list compact">
                    {items.map((handoff) => (
                      <article
                        className={`list-card selectable-card ${activeHandoff?.id === handoff.id ? "selected-card" : ""}`}
                        key={handoff.id}
                        onClick={() => setSelectedHandoffId(handoff.id)}
                      >
                        <div className="row spread">
                          <div>
                            <h4>{handoff.project_name || handoff.project_id}</h4>
                            <p>{handoff.reason}</p>
                          </div>
                          <StatusChip value={handoff.status} />
                        </div>
                        <KeyValueList
                          items={[
                            { label: "from", value: handoff.from_actor },
                            { label: "created", value: formatDateTime(handoff.created_at) },
                            { label: "resolved", value: formatDateTime(handoff.resolved_at) },
                          ]}
                        />
                      </article>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <Section title="Handoff detail" eyebrow="Panel" stagger={1}>
              {!activeHandoff ? (
                <StateScreen title="Sin handoff seleccionado" body="Elegi un handoff del inbox para ver el detalle." />
              ) : (
                <div className="stack-list">
                  <article className="list-card">
                    <div className="row spread">
                      <div>
                        <h4>{activeHandoff.project_name || activeHandoff.project_id}</h4>
                        <p>{activeHandoff.id}</p>
                      </div>
                      <StatusChip value={activeHandoff.status} />
                    </div>
                    <KeyValueList
                      items={[
                        { label: "from actor", value: activeHandoff.from_actor },
                        { label: "to actor", value: activeHandoff.to_actor },
                        { label: "reason", value: activeHandoff.reason },
                        { label: "created", value: formatDateTime(activeHandoff.created_at) },
                        { label: "resolved", value: formatDateTime(activeHandoff.resolved_at) },
                        { label: "from run", value: activeHandoff.from_run_id || "-" },
                        { label: "resolved by", value: activeHandoff.resolved_by_run_id || "-" },
                      ]}
                    />
                  </article>
                  <article className="list-card">
                    <div className="eyebrow">Message</div>
                    <p className="rich-copy">{activeHandoff.message || "Sin mensaje persistido."}</p>
                  </article>
                  <article className="list-card">
                    <div className="eyebrow">Context refs</div>
                    {activeHandoff.context_refs.length === 0 ? (
                      <p className="muted-copy">No hay referencias contextuales en este handoff.</p>
                    ) : (
                      <div className="pill-cluster">
                        {activeHandoff.context_refs.map((item) => (
                          <span className="meta-pill" key={item}>
                            {item}
                          </span>
                        ))}
                      </div>
                    )}
                  </article>
                  <article className="list-card">
                    <div className="eyebrow">Resolve</div>
                    <textarea
                      className="inline-textarea"
                      onChange={(event) => setResolutionNote(event.target.value)}
                      placeholder="Optional resolution note"
                      rows={4}
                      value={resolutionNote}
                    />
                    <div className="task-actions">
                      <button className="primary-button" disabled={resolveHandoffMutation.isPending} onClick={handleResolveHandoff} type="button">
                        {resolveHandoffMutation.isPending ? "Resolving..." : "Resolve"}
                      </button>
                    </div>
                  </article>
                </div>
              )}
            </Section>
          </div>
        )}
      </Section>
    </AppShell>
  );
}

function parseTagsInput(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function TaskCountsCluster({ counts }: { counts: TaskCounts }) {
  return (
    <div className="pill-cluster task-count-cluster">
      {taskStatusOrder.map((status) => (
        <span className="meta-pill" key={status}>
          {taskStatusLabels[status]}: {formatNumber(counts[status])}
        </span>
      ))}
      <span className="meta-pill">Total: {formatNumber(counts.total)}</span>
    </div>
  );
}
function IdeaTreeCard({
  idea,
  active,
  onSelect,
}: {
  idea: IdeasOverviewResponse["ideas"][number];
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <article className={`idea-tree-card reveal selectable-card ${active ? "selected-card" : ""}`} onClick={onSelect}>
      <div className="idea-tree-rail" />
      <div className="idea-tree-body">
        <div className="row spread">
          <div>
            <div className="idea-tree-title">{truncateText(idea.title || idea.raw_text, 72)}</div>
            <div className="idea-tree-subtitle">{idea.project_name || idea.project_id || "Sin proyecto asociado"}</div>
          </div>
          <StatusChip value={idea.status} />
        </div>

        <div className="idea-tree-meta">
          <span>{idea.source}</span>
          <span>{formatDateTime(idea.created_at)}</span>
        </div>

        <TaskCountsCluster counts={idea.task_counts} />
      </div>
    </article>
  );
}

function IdeaDetailHero({ idea }: { idea: IdeaWorkspaceResponse["idea"] }) {
  return (
    <article className="list-card idea-detail-hero">
      <div className="row spread">
        <div>
          <div className="eyebrow">Focused idea</div>
          <h4>{idea.title}</h4>
          <p>{idea.project_name || idea.project_id || "Sin proyecto asociado"}</p>
        </div>
        <StatusChip value={idea.status} />
      </div>

      <p className="rich-copy">{idea.raw_text}</p>

      <div className="idea-detail-grid">
        <div>
          <div className="eyebrow">Source</div>
          <p>{idea.source}</p>
        </div>
        <div>
          <div className="eyebrow">Created</div>
          <p>{formatDateTime(idea.created_at)}</p>
        </div>
        <div>
          <div className="eyebrow">Triaged</div>
          <p>{formatDateTime(idea.triaged_at)}</p>
        </div>
        <div>
          <div className="eyebrow">Promoted to</div>
          <p>{idea.promoted_to || "-"}</p>
        </div>
      </div>

      {idea.tags.length ? (
        <div className="pill-cluster">
          {idea.tags.map((tag) => (
            <span className="meta-pill" key={tag}>
              #{tag}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted-copy">Esta idea no tiene tags persistidos.</p>
      )}
    </article>
  );
}

function SplitArrowTaskCard({
  task,
  index,
  isEditing,
  editingDraft,
  setEditingDraft,
  startEditingTask,
  setEditingTaskId,
  handleSaveTask,
  handleDeleteTask,
  handleTaskStatusChange,
  updateTaskPending,
  deleteTaskPending,
}: {
  task: TaskRecord;
  index: number;
  isEditing: boolean;
  editingDraft: {
    title: string;
    description: string;
    status: TaskStatus;
    priority: number;
    tagsText: string;
  };
  setEditingDraft: React.Dispatch<
    React.SetStateAction<{
      title: string;
      description: string;
      status: TaskStatus;
      priority: number;
      tagsText: string;
    }>
  >;
  startEditingTask: (task: TaskRecord) => void;
  setEditingTaskId: React.Dispatch<React.SetStateAction<string | null>>;
  handleSaveTask: (taskId: string) => Promise<void>;
  handleDeleteTask: (taskId: string) => Promise<void>;
  handleTaskStatusChange: (taskId: string, status: TaskStatus) => Promise<void>;
  updateTaskPending: boolean;
  deleteTaskPending: boolean;
}) {
  return (
    <article className={`task-arrow-card status-${task.status}`}>
      <div className="task-arrow-tail" />
      <div className="task-arrow-index">{index + 1}</div>
      <div className="task-arrow-body">
        {isEditing ? (
          <div className="stack-list compact">
            <input
              value={editingDraft.title}
              onChange={(event) => setEditingDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder="Task title"
            />
            <textarea
              value={editingDraft.description}
              onChange={(event) => setEditingDraft((current) => ({ ...current, description: event.target.value }))}
              placeholder="Task description"
              rows={3}
            />
            <div className="task-form-grid">
              <select
                value={editingDraft.status}
                onChange={(event) => setEditingDraft((current) => ({ ...current, status: event.target.value as TaskStatus }))}
              >
                {taskStatusOrder.map((status) => (
                  <option key={status} value={status}>
                    {taskStatusLabels[status]}
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={editingDraft.priority}
                onChange={(event) => setEditingDraft((current) => ({ ...current, priority: Number(event.target.value) }))}
              />
            </div>
            <input
              value={editingDraft.tagsText}
              onChange={(event) => setEditingDraft((current) => ({ ...current, tagsText: event.target.value }))}
              placeholder="tags, comma, separated"
            />
            <div className="task-actions">
              <button className="primary-button" disabled={updateTaskPending} onClick={() => handleSaveTask(task.id)} type="button">
                Save
              </button>
              <button className="secondary-button" onClick={() => setEditingTaskId(null)} type="button">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="stack-list compact">
            <div className="row spread">
              <div>
                <h4>{task.title}</h4>
                <p>{task.description || "No description persisted."}</p>
              </div>
              <StatusChip value={task.status} />
            </div>
            <div className="task-arrow-meta">
              <span>Priority {task.priority}</span>
              <span>Position {task.position}</span>
              <span>{formatDateTime(task.updated_at)}</span>
            </div>
            {task.tags.length ? (
              <div className="pill-cluster">
                {task.tags.map((tag) => (
                  <span className="meta-pill" key={tag}>
                    #{tag}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="task-actions task-actions-inline">
              <select value={task.status} onChange={(event) => handleTaskStatusChange(task.id, event.target.value as TaskStatus)}>
                {taskStatusOrder.map((status) => (
                  <option key={status} value={status}>
                    {taskStatusLabels[status]}
                  </option>
                ))}
              </select>
              <button className="secondary-button" onClick={() => startEditingTask(task)} type="button">
                Edit
              </button>
              <button
                className="danger-button"
                disabled={deleteTaskPending}
                onClick={() => handleDeleteTask(task.id)}
                type="button"
              >
                Delete
              </button>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function IdeasPage() {
  const queryClient = useQueryClient();
  const [subview, setSubview] = useState<IdeasSubview>("tree");
  const [filters, setFilters] = useState({
    status: "",
    source: "",
    q: "",
  });
  const [selectedIdeaId, setSelectedIdeaId] = useState<string | null>(null);
  const [taskDraft, setTaskDraft] = useState({
    title: "",
    description: "",
    status: "backlog" as TaskStatus,
    priority: 0,
    tagsText: "",
  });
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState({
    title: "",
    description: "",
    status: "backlog" as TaskStatus,
    priority: 0,
    tagsText: "",
  });
  const [taskError, setTaskError] = useState<string | null>(null);
  const [ideaError, setIdeaError] = useState<string | null>(null);
  const [ideaActionMessage, setIdeaActionMessage] = useState<string | null>(null);
  const [triageDraft, setTriageDraft] = useState({
    status: "",
    project_id: "",
    triage_notes: "",
    promoted_to: "",
  });
  const deferredFilters = useDeferredValue(filters);

  const ideasQuery = useQuery({
    queryKey: ["dashboard-ideas"],
    queryFn: getIdeasOverview,
  });
  const projectsQuery = useQuery({
    queryKey: ["dashboard-projects", "for-triage"],
    queryFn: () => getProjects({}),
  });

  const data = ideasQuery.data as IdeasOverviewResponse | undefined;
  const rows = (data?.ideas ?? []).filter((idea) => {
    const matchesStatus = !deferredFilters.status || idea.status === deferredFilters.status;
    const matchesSource = !deferredFilters.source || idea.source === deferredFilters.source;
    const query = deferredFilters.q.trim().toLowerCase();
    const haystack = `${idea.title} ${idea.raw_text}`.toLowerCase();
    return matchesStatus && matchesSource && (!query || haystack.includes(query));
  });
  const activeIdea = rows.find((idea) => idea.id === selectedIdeaId) || rows[0] || null;

  const workspaceQuery = useQuery({
    queryKey: ["dashboard-idea-workspace", activeIdea?.id],
    queryFn: () => getIdeaWorkspace(activeIdea!.id),
    enabled: Boolean(activeIdea?.id),
  });
  const boardQuery = useQuery({
    queryKey: ["dashboard-tasks-board", activeIdea?.id],
    queryFn: () => getTasksBoard(activeIdea?.id ? { idea_id: activeIdea.id } : undefined),
  });
  const workspace = workspaceQuery.data as IdeaWorkspaceResponse | undefined;
  const board = boardQuery.data as TasksBoardResponse | undefined;

  const invalidateIdeasData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard-ideas"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-idea-workspace"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-tasks-board"] }),
    ]);
  };

  const createTaskMutation = useMutation({
    mutationFn: createTask,
    onSuccess: async () => {
      setTaskError(null);
      setTaskDraft({
        title: "",
        description: "",
        status: "backlog",
        priority: 0,
        tagsText: "",
      });
      await invalidateIdeasData();
    },
    onError: (error: Error) => setTaskError(error.message),
  });
  const updateTaskMutation = useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: Parameters<typeof updateTask>[1] }) => updateTask(taskId, payload),
    onSuccess: async () => {
      setTaskError(null);
      await invalidateIdeasData();
    },
    onError: (error: Error) => setTaskError(error.message),
  });
  const deleteTaskMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: async () => {
      setTaskError(null);
      setEditingTaskId(null);
      await invalidateIdeasData();
    },
    onError: (error: Error) => setTaskError(error.message),
  });
  const triageIdeaMutation = useMutation({
    mutationFn: ({ ideaId, payload }: { ideaId: string; payload: Parameters<typeof triageIdea>[1] }) => triageIdea(ideaId, payload),
    onSuccess: async () => {
      setIdeaError(null);
      setIdeaActionMessage("Idea triaged successfully.");
      await Promise.all([
        invalidateIdeasData(),
        queryClient.invalidateQueries({ queryKey: ["dashboard-projects"] }),
      ]);
    },
    onError: (error: Error) => {
      setIdeaActionMessage(null);
      setIdeaError(error.message);
    },
  });

  useEffect(() => {
    if (!workspace?.idea) {
      return;
    }
    setTriageDraft({
      status: workspace.idea.status || "",
      project_id: workspace.idea.project_id || "",
      triage_notes: workspace.idea.triage_notes || "",
      promoted_to: workspace.idea.promoted_to || "",
    });
  }, [
    workspace?.idea?.id,
    workspace?.idea?.status,
    workspace?.idea?.project_id,
    workspace?.idea?.triage_notes,
    workspace?.idea?.promoted_to,
  ]);

  function startEditingTask(task: TaskRecord) {
    setEditingTaskId(task.id);
    setEditingDraft({
      title: task.title,
      description: task.description || "",
      status: task.status,
      priority: task.priority,
      tagsText: task.tags.join(", "),
    });
  }

  async function handleCreateTask(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeIdea) {
      return;
    }
    await createTaskMutation.mutateAsync({
      idea_id: activeIdea.id,
      project_id: activeIdea.project_id,
      title: taskDraft.title,
      description: taskDraft.description || null,
      status: taskDraft.status,
      priority: Number(taskDraft.priority) || 0,
      tags: parseTagsInput(taskDraft.tagsText),
    });
  }

  async function handleSaveTask(taskId: string) {
    await updateTaskMutation.mutateAsync({
      taskId,
      payload: {
        title: editingDraft.title,
        description: editingDraft.description || null,
        status: editingDraft.status,
        priority: Number(editingDraft.priority) || 0,
        tags: parseTagsInput(editingDraft.tagsText),
      },
    });
    setEditingTaskId(null);
  }

  async function handleDeleteTask(taskId: string) {
    if (!window.confirm("Delete this task? This action cannot be undone.")) {
      return;
    }
    await deleteTaskMutation.mutateAsync(taskId);
  }

  async function handleTaskStatusChange(taskId: string, status: TaskStatus) {
    await updateTaskMutation.mutateAsync({
      taskId,
      payload: { status },
    });
  }

  async function handleIdeaTriage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeIdea) {
      return;
    }
    setIdeaActionMessage(null);
    setIdeaError(null);
    await triageIdeaMutation.mutateAsync({
      ideaId: activeIdea.id,
      payload: {
        status: triageDraft.status ? (triageDraft.status as "new" | "triaged" | "promoted" | "discarded") : undefined,
        project_id: triageDraft.project_id || null,
        triage_notes: triageDraft.triage_notes || null,
        promoted_to: triageDraft.promoted_to || null,
      },
    });
  }

  async function moveBoardTask(task: TaskRecord, direction: -1 | 1) {
    const currentIndex = taskStatusOrder.indexOf(task.status);
    const nextStatus = taskStatusOrder[currentIndex + direction];
    if (!nextStatus) {
      return;
    }
    const nextColumn = board?.[nextStatus] || [];
    await updateTaskMutation.mutateAsync({
      taskId: task.id,
      payload: { status: nextStatus, position: nextColumn.length },
    });
  }

  async function moveTaskWithinBoardColumn(task: TaskRecord, direction: -1 | 1) {
    const column = board?.[task.status] || [];
    const currentIndex = column.findIndex((item) => item.id === task.id);
    const targetTask = column[currentIndex + direction];
    if (!targetTask) {
      return;
    }
    await updateTaskMutation.mutateAsync({
      taskId: task.id,
      payload: { position: targetTask.position },
    });
  }

  if (ideasQuery.isLoading) {
    return (
      <AppShell title="Ideas" subtitle="Ideas workspace with real task CRUD, workspace detail and board view.">
        <div className="kpi-grid ideas-kpis">
          {Array.from({ length: 5 }).map((_, index) => (
            <SkeletonBlock key={index} height={130} />
          ))}
        </div>
        <SkeletonBlock height={120} />
        <div className="detail-layout">
          <SkeletonBlock height={560} />
          <SkeletonBlock height={560} />
        </div>
      </AppShell>
    );
  }

  if (ideasQuery.isError) {
    return (
      <AppShell title="Ideas" subtitle="Ideas workspace with real task CRUD, workspace detail and board view.">
        <StateScreen title="No pude cargar ideas" body={ideasQuery.error.message} tone="bad" />
      </AppShell>
    );
  }
  return (
    <AppShell title="Ideas" subtitle="Ideas workspace with real task CRUD, task aggregates and a board grounded in persisted tasks.">
      <div className="kpi-grid ideas-kpis">
        <KpiCard label="Total" value={data!.kpis.total} note="ideas persisted in intake" stagger={0} />
        <KpiCard label="New" value={data!.kpis.new} note="still waiting for triage" stagger={1} />
        <KpiCard label="Triaged" value={data!.kpis.triaged} note="already reviewed or attached" stagger={2} />
        <KpiCard label="Promoted" value={data!.kpis.promoted} note="promoted to another outcome" stagger={3} />
        <KpiCard label="Discarded" value={data!.kpis.discarded} note="discarded explicitly" stagger={4} />
      </div>

      <div className="dashboard-grid ideas-summary-grid">
        <Section title="Sources" eyebrow="Counts by source" stagger={5}>
          <div className="pill-cluster">
            {Object.entries(data!.sources).map(([source, count]) => (
              <span className="meta-pill" key={source}>
                {source}: {formatNumber(count)}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Tasks distribution" eyebrow="Real aggregates" stagger={6}>
          <TaskCountsCluster counts={data!.task_kpis} />
        </Section>
      </div>

      <Section
        title="Ideas workspace"
        eyebrow="Phase 2 foundation"
        aside={
          <div className="tabs">
            {ideasSubviewOptions.map((option) => (
              <button
                key={option.value}
                className={subview === option.value ? "active" : ""}
                onClick={() => setSubview(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
        }
        stagger={7}
      >
        <div className="filters">
          <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
            <option value="">Todos los status</option>
            <option value="new">new</option>
            <option value="triaged">triaged</option>
            <option value="promoted">promoted</option>
            <option value="discarded">discarded</option>
          </select>
          <select value={filters.source} onChange={(event) => setFilters((current) => ({ ...current, source: event.target.value }))}>
            <option value="">Todas las fuentes</option>
            <option value="telegram">telegram</option>
            <option value="whatsapp">whatsapp</option>
            <option value="cli">cli</option>
            <option value="web">web</option>
            <option value="other">other</option>
          </select>
          <input
            value={filters.q}
            onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
            placeholder="buscar por title o raw_text"
          />
          <div className="meta-pill filter-pill">{rows.length} visibles</div>
        </div>

        {taskError ? <p className="form-error">{taskError}</p> : null}
        {ideaError ? <p className="form-error">{ideaError}</p> : null}
        {ideaActionMessage ? <p className="form-success">{ideaActionMessage}</p> : null}

        {rows.length === 0 ? (
          <StateScreen title="Sin ideas" body="No hay ideas para los filtros actuales." />
        ) : subview === "board" ? (
          boardQuery.isLoading ? (
            <div className="board-grid">
              {taskStatusOrder.map((status) => (
                <SkeletonBlock key={status} height={420} />
              ))}
            </div>
          ) : boardQuery.isError ? (
            <StateScreen title="No pude cargar el board" body={boardQuery.error.message} tone="bad" />
          ) : (
            <div className="board-grid">
              {taskStatusOrder.map((status, columnIndex) => (
                <article className="board-column reveal" key={status} style={{ "--stagger": columnIndex } as React.CSSProperties}>
                  <div className="row spread board-column-head">
                    <div>
                      <div className="eyebrow">column</div>
                      <h4>{taskStatusLabels[status]}</h4>
                    </div>
                    <span className="meta-pill">{board?.[status]?.length || 0}</span>
                  </div>

                  <div className="stack-list compact">
                    {(board?.[status] || []).length === 0 ? (
                      <p className="muted-copy">
                        {activeIdea ? "No tasks in this column for the selected idea yet." : "No tasks in this column yet."}
                      </p>
                    ) : (
                      (board?.[status] || []).map((task) => (
                        <article
                          className={`list-card board-task-card ${task.idea_id === activeIdea?.id ? "board-task-active-idea" : ""}`}
                          key={task.id}
                        >
                          <div className="row spread">
                            <div>
                              <h4>{task.title}</h4>
                              <p>{task.idea_title || "Task without linked idea title"}</p>
                            </div>
                            <StatusChip value={task.status} />
                          </div>
                          <p className="rich-copy">{task.description || task.idea_summary || "No description persisted."}</p>
                          <KeyValueList
                            items={[
                              { label: "priority", value: task.priority },
                              { label: "position", value: task.position },
                              { label: "updated", value: formatDateTime(task.updated_at) },
                            ]}
                          />
                          {task.tags.length === 0 ? null : (
                            <div className="pill-cluster">
                              {task.tags.map((tag) => (
                                <span className="meta-pill" key={tag}>
                                  #{tag}
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="task-actions">
                            <button
                              className="secondary-button"
                              disabled={updateTaskMutation.isPending || !((board?.[status] || []).findIndex((item) => item.id === task.id) > 0)}
                              onClick={() => moveTaskWithinBoardColumn(task, -1)}
                              type="button"
                            >
                              Up
                            </button>
                            <button
                              className="secondary-button"
                              disabled={
                                updateTaskMutation.isPending ||
                                (board?.[status] || []).findIndex((item) => item.id === task.id) === (board?.[status] || []).length - 1
                              }
                              onClick={() => moveTaskWithinBoardColumn(task, 1)}
                              type="button"
                            >
                              Down
                            </button>
                            <button
                              className="secondary-button"
                              disabled={updateTaskMutation.isPending || taskStatusOrder.indexOf(task.status) === 0}
                              onClick={() => moveBoardTask(task, -1)}
                              type="button"
                            >
                              Move left
                            </button>
                            <button
                              className="secondary-button"
                              disabled={
                                updateTaskMutation.isPending || taskStatusOrder.indexOf(task.status) === taskStatusOrder.length - 1
                              }
                              onClick={() => moveBoardTask(task, 1)}
                              type="button"
                            >
                              Move right
                            </button>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                </article>
              ))}
            </div>
          )
        ) : (
          <div className="detail-layout">
            <div className="stack-list">
              {rows.map((idea, index) => (
                <div key={idea.id} style={{ "--stagger": index } as React.CSSProperties}>
                  <IdeaTreeCard idea={idea} active={activeIdea?.id === idea.id} onSelect={() => setSelectedIdeaId(idea.id)} />
                </div>
              ))}
            </div>

            <Section
              title={subview === "tree" ? "Idea detail" : "Tasks workspace"}
              eyebrow={subview === "tree" ? "Derived from legacy idea schema" : "Inline CRUD"}
              stagger={1}
            >
              {!activeIdea ? (
                <StateScreen title="Sin idea seleccionada" body="Elegi una idea para ver su workspace." />
              ) : workspaceQuery.isLoading ? (
                <div className="stack-list">
                  <SkeletonBlock height={220} />
                  <SkeletonBlock height={200} />
                  <SkeletonBlock height={180} />
                </div>
              ) : workspaceQuery.isError ? (
                <StateScreen title="No pude cargar el workspace" body={workspaceQuery.error.message} tone="bad" />
              ) : subview === "tree" ? (
                <div className="stack-list">
                  <IdeaDetailHero idea={workspace!.idea} />

                  <form className="task-form list-card" onSubmit={handleIdeaTriage}>
                    <div className="eyebrow">Triage</div>
                    <div className="inline-form-grid">
                      <select
                        value={triageDraft.status}
                        onChange={(event) => setTriageDraft((current) => ({ ...current, status: event.target.value }))}
                      >
                        <option value="">Keep current status</option>
                        <option value="new">new</option>
                        <option value="triaged">triaged</option>
                        <option value="promoted">promoted</option>
                        <option value="discarded">discarded</option>
                      </select>
                      <select
                        value={triageDraft.project_id}
                        onChange={(event) => setTriageDraft((current) => ({ ...current, project_id: event.target.value }))}
                      >
                        <option value="">Sin proyecto</option>
                        {(projectsQuery.data ?? []).map((project) => (
                          <option key={project.id} value={project.id}>
                            {project.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <textarea
                      value={triageDraft.triage_notes}
                      onChange={(event) => setTriageDraft((current) => ({ ...current, triage_notes: event.target.value }))}
                      placeholder="Triage notes"
                      rows={4}
                    />
                    <input
                      value={triageDraft.promoted_to}
                      onChange={(event) => setTriageDraft((current) => ({ ...current, promoted_to: event.target.value }))}
                      placeholder="promoted_to (optional)"
                    />
                    <div className="task-actions">
                      <button className="primary-button" disabled={triageIdeaMutation.isPending} type="submit">
                        {triageIdeaMutation.isPending ? "Saving..." : "Save triage"}
                      </button>
                    </div>
                  </form>

                  <article className="list-card">
                    <div className="eyebrow">Task posture</div>
                    <TaskCountsCluster counts={workspace!.idea.task_counts} />
                    <p className="panel-note">
                      Esta subvista mantiene el modelo actual: `title` sigue derivado desde `raw_text`, y la jerarquía visible se construye desde tags y task counts en vez de un árbol persistido de ideas padre/hija.
                    </p>
                  </article>

                  <article className="list-card">
                    <div className="eyebrow">Sibling ideas in same tag</div>
                    {workspace?.sibling_ideas_in_same_tag.length ? (
                      <div className="stack-list compact">
                        {workspace.sibling_ideas_in_same_tag.map((idea) => (
                          <article className="nested-list-card" key={idea.id}>
                            <div className="row spread">
                              <div>
                                <h4>{idea.title}</h4>
                                <p>{idea.project_name || idea.project_id || "Sin proyecto asociado"}</p>
                              </div>
                              <StatusChip value={idea.status} />
                            </div>
                            <TaskCountsCluster counts={idea.task_counts} />
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="muted-copy">No sibling ideas were found from the currently persisted tags.</p>
                    )}
                  </article>

                  <article className="list-card">
                    <div className="eyebrow">Current tasks</div>
                    {workspace?.tasks.length ? (
                      <div className="stack-list compact">
                        {workspace.tasks.map((task) => (
                          <article className="nested-list-card" key={task.id}>
                            <div className="row spread">
                              <div>
                                <h4>{task.title}</h4>
                                <p>{task.description || "No description persisted."}</p>
                              </div>
                              <StatusChip value={task.status} />
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="muted-copy">This idea still has no tasks. Use the Tasks tab to create the first one.</p>
                    )}
                  </article>
                </div>
              ) : (
                <div className="stack-list">
                  <div className="split-arrow-layout">
                    <div className="split-root-column">
                      <article className="idea-root-card">
                        <div className="eyebrow">Idea root</div>
                        <h4>{workspace?.idea.title}</h4>
                        <p>{workspace?.idea.raw_text}</p>
                        <TaskCountsCluster counts={workspace?.idea.task_counts || data!.task_kpis} />
                        <div className="pill-cluster">
                          <span className="meta-pill">{workspace?.idea.source}</span>
                          <span className="meta-pill">{workspace?.idea.project_name || workspace?.idea.project_id || "Sin proyecto"}</span>
                        </div>
                      </article>
                    </div>

                    <div className="split-arrow-workspace">
                      <form className="task-form list-card" onSubmit={handleCreateTask}>
                        <div className="eyebrow">Create task</div>
                        <input
                          value={taskDraft.title}
                          onChange={(event) => setTaskDraft((current) => ({ ...current, title: event.target.value }))}
                          placeholder="Task title"
                        />
                        <textarea
                          value={taskDraft.description}
                          onChange={(event) => setTaskDraft((current) => ({ ...current, description: event.target.value }))}
                          placeholder="Optional description"
                          rows={4}
                        />
                        <div className="task-form-grid">
                          <select
                            value={taskDraft.status}
                            onChange={(event) =>
                              setTaskDraft((current) => ({ ...current, status: event.target.value as TaskStatus }))
                            }
                          >
                            {taskStatusOrder.map((status) => (
                              <option key={status} value={status}>
                                {taskStatusLabels[status]}
                              </option>
                            ))}
                          </select>
                          <input
                            type="number"
                            value={taskDraft.priority}
                            onChange={(event) => setTaskDraft((current) => ({ ...current, priority: Number(event.target.value) }))}
                            placeholder="Priority"
                          />
                        </div>
                        <input
                          value={taskDraft.tagsText}
                          onChange={(event) => setTaskDraft((current) => ({ ...current, tagsText: event.target.value }))}
                          placeholder="tags, comma, separated"
                        />
                        <div className="task-actions">
                          <button className="primary-button" disabled={createTaskMutation.isPending} type="submit">
                            {createTaskMutation.isPending ? "Creating..." : "Create task"}
                          </button>
                        </div>
                      </form>

                      {workspace?.tasks.length ? (
                        workspace.tasks.map((task, index) => (
                          <SplitArrowTaskCard
                            key={task.id}
                            task={task}
                            index={index}
                            isEditing={editingTaskId === task.id}
                            editingDraft={editingDraft}
                            setEditingDraft={setEditingDraft}
                            startEditingTask={startEditingTask}
                            setEditingTaskId={setEditingTaskId}
                            handleSaveTask={handleSaveTask}
                            handleDeleteTask={handleDeleteTask}
                            handleTaskStatusChange={handleTaskStatusChange}
                            updateTaskPending={updateTaskMutation.isPending}
                            deleteTaskPending={deleteTaskMutation.isPending}
                          />
                        ))
                      ) : (
                        <StateScreen title="No tasks yet" body="Create the first task inline to turn this idea into a usable workspace." />
                      )}
                    </div>
                  </div>
                </div>
              )}
            </Section>
          </div>
        )}
      </Section>

      <Section title="Scope note" eyebrow="Honest schema" stagger={8}>
        <p className="panel-note">
          F2B consolida la Opción A: `ideas.title` y `ideas.description` siguen derivados desde `raw_text`. No abrí una migración nueva porque el schema actual ya soporta el flujo y el riesgo no justificaba duplicar datos antes de graph. El board mantiene move actions explícitas, más orden por `position`, porque hoy es más robusto y menos frágil que un DnD apresurado.
        </p>
      </Section>
    </AppShell>
  );
}

function notificationSubjectLabel(item: NotificationEventRecord) {
  return item.project_name || item.candidate_name || item.idea_title || item.task_title || item.project_id || item.candidate_id || "Unscoped event";
}

function NotificationsPage() {
  const [filters, setFilters] = useState({
    channel: "",
    direction: "",
    delivery_status: "",
    project_id: "",
  });
  const deferredFilters = useDeferredValue(filters);
  const listQuery = useQuery({
    queryKey: ["dashboard-notifications", deferredFilters],
    queryFn: () => getNotifications(deferredFilters),
  });
  const telegramQuery = useQuery({
    queryKey: ["dashboard-telegram-summary"],
    queryFn: getTelegramSummary,
  });
  const notifications = (listQuery.data as DashboardNotificationsResponse | undefined)?.items || [];
  const summary = (listQuery.data as DashboardNotificationsResponse | undefined)?.summary;
  const telegramSummary = telegramQuery.data as TelegramSummaryResponse | undefined;

  const [selectedNotificationId, setSelectedNotificationId] = useState<string | null>(null);
  useEffect(() => {
    if (!notifications.length) {
      if (selectedNotificationId !== null) {
        setSelectedNotificationId(null);
      }
      return;
    }
    if (!selectedNotificationId || !notifications.some((item) => item.id === selectedNotificationId)) {
      setSelectedNotificationId(notifications[0]?.id || null);
    }
  }, [notifications, selectedNotificationId]);

  const detailQuery = useQuery({
    queryKey: ["dashboard-notification-detail", selectedNotificationId],
    queryFn: () => getNotificationDetail(selectedNotificationId || ""),
    enabled: Boolean(selectedNotificationId),
  });

  const queryError = listQuery.isError
    ? listQuery.error
    : telegramQuery.isError
      ? telegramQuery.error
      : detailQuery.isError
        ? detailQuery.error
        : null;

  if (listQuery.isLoading || telegramQuery.isLoading) {
    return (
      <AppShell title="Notifications" subtitle="Historial read-only de Telegram y otros eventos persistidos por el runtime.">
        <SkeletonBlock height={220} />
        <SkeletonBlock height={520} />
      </AppShell>
    );
  }

  if (queryError || !summary) {
    return (
      <AppShell title="Notifications" subtitle="Historial read-only de Telegram y otros eventos persistidos por el runtime.">
        <StateScreen title="No pude cargar notifications" body={queryError ? queryError.message : "Missing notifications payload"} tone="bad" />
      </AppShell>
    );
  }

  const selectedNotification = detailQuery.data as NotificationEventRecord | undefined;

  return (
    <AppShell
      title="Notifications"
      subtitle="Foundation read-only de notification events. Si no hubo persistencia real todavía, la UI muestra vacío honesto."
    >
      <div className="kpi-grid langfuse-kpis">
        <KpiCard label="Events" value={summary.total} note="notification_events persistidos" stagger={0} />
        <KpiCard label="Telegram" value={summary.telegram} note="eventos del canal telegram" stagger={1} />
        <KpiCard label="Inbound" value={summary.inbound} note="idea capture y otros inbound" stagger={2} />
        <KpiCard label="Outbound" value={summary.outbound} note="summaries y prompts enviados" stagger={3} />
        <KpiCard label="Delivered" value={summary.delivered} note="entregas marcadas como delivered" stagger={4} />
      </div>

      <div className="dashboard-grid">
        <Section title="Telegram summary" eyebrow="Read-only aggregate" stagger={1}>
          {telegramSummary && telegramSummary.message_types.length > 0 ? (
            <div className="stack-list compact">
              {telegramSummary.message_types.map((item, index) => (
                <article className="list-card reveal" key={item.message_type} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <h4>{item.message_type}</h4>
                    <span className="meta-pill">{formatNumber(item.count)} events</span>
                  </div>
                  <p>Counter agregado desde `notification_events` para Telegram.</p>
                </article>
              ))}
            </div>
          ) : (
            <StateScreen title="Sin eventos de Telegram todavía" body="La estructura está lista; cuando entren o salgan mensajes persistidos van a aparecer acá." />
          )}
        </Section>

        <Section title="How to read this" eyebrow="Honest instrumentation" stagger={2}>
          <div className="stack-list">
            <article className="list-card">
              <h4>No inventamos activity</h4>
              <p>Si todavía no se persistió un tipo de evento, el dashboard muestra vacío o `unknown` y no un estado fabricado.</p>
            </article>
            <article className="list-card">
              <h4>Telegram first</h4>
              <p>Esta primera base prioriza inbound idea capture y outbound daily summaries, que son los hooks más claros del runtime actual.</p>
            </article>
          </div>
        </Section>
      </div>

      <Section title="Events table" eyebrow="Persisted history" stagger={3} aside={<span className="meta-pill">{notifications.length} rows</span>}>
        <div className="filters">
          <select value={filters.channel} onChange={(event) => setFilters((current) => ({ ...current, channel: event.target.value }))}>
            <option value="">Todos los channels</option>
            <option value="telegram">telegram</option>
            <option value="system">system</option>
          </select>
          <select value={filters.direction} onChange={(event) => setFilters((current) => ({ ...current, direction: event.target.value }))}>
            <option value="">Todas las direcciones</option>
            <option value="inbound">inbound</option>
            <option value="outbound">outbound</option>
            <option value="system">system</option>
          </select>
          <select
            value={filters.delivery_status}
            onChange={(event) => setFilters((current) => ({ ...current, delivery_status: event.target.value }))}
          >
            <option value="">Todos los delivery_status</option>
            <option value="delivered">delivered</option>
            <option value="received">received</option>
            <option value="failed">failed</option>
            <option value="pending">pending</option>
          </select>
          <input
            value={filters.project_id}
            onChange={(event) => setFilters((current) => ({ ...current, project_id: event.target.value }))}
            placeholder="project_id"
          />
        </div>

        {notifications.length === 0 ? (
          <StateScreen title="No hay notification events" body="Todavía no hay eventos persistidos para estos filtros." />
        ) : (
          <div className="detail-layout">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>summary</th>
                    <th>channel</th>
                    <th>direction</th>
                    <th>status</th>
                    <th>message type</th>
                    <th>subject</th>
                    <th>created</th>
                  </tr>
                </thead>
                <tbody>
                  {notifications.map((item) => (
                    <tr
                      key={item.id}
                      className={item.id === selectedNotificationId ? "selected-row" : ""}
                      onClick={() => setSelectedNotificationId(item.id)}
                    >
                      <td>{item.summary || "—"}</td>
                      <td>{item.channel}</td>
                      <td>{item.direction}</td>
                      <td><StatusChip value={item.delivery_status} live={item.delivery_status === "delivered"} /></td>
                      <td>{item.message_type || "—"}</td>
                      <td>{notificationSubjectLabel(item)}</td>
                      <td>{formatDateTime(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="detail-panel">
              {selectedNotification ? (
                <Section title="Notification detail" eyebrow="Selected event" stagger={4}>
                  <article className="list-card">
                    <div className="row spread">
                      <h4>{selectedNotification.summary || selectedNotification.message_type || selectedNotification.id}</h4>
                      <StatusChip value={selectedNotification.delivery_status} live={selectedNotification.delivery_status === "delivered"} />
                    </div>
                    <p>{notificationSubjectLabel(selectedNotification)}</p>
                    <KeyValueList
                      items={[
                        { label: "channel", value: selectedNotification.channel },
                        { label: "direction", value: selectedNotification.direction },
                        { label: "message_type", value: selectedNotification.message_type || "—" },
                        { label: "project", value: selectedNotification.project_name || selectedNotification.project_id || "—" },
                        { label: "candidate", value: selectedNotification.candidate_name || selectedNotification.candidate_id || "—" },
                        { label: "idea", value: selectedNotification.idea_title || selectedNotification.idea_id || "—" },
                        { label: "task", value: selectedNotification.task_title || selectedNotification.task_id || "—" },
                        { label: "external_ref", value: selectedNotification.external_ref || "—" },
                        { label: "created", value: formatDateTime(selectedNotification.created_at) },
                        { label: "delivered", value: formatDateTime(selectedNotification.delivered_at) },
                      ]}
                    />
                    {Object.keys(selectedNotification.payload_summary).length ? (
                      <pre className="detail-json">{JSON.stringify(selectedNotification.payload_summary, null, 2)}</pre>
                    ) : null}
                    {selectedNotification.error_summary ? <p className="form-error">{selectedNotification.error_summary}</p> : null}
                  </article>
                </Section>
              ) : (
                <StateScreen title="Sin evento seleccionado" body="Elegí una fila para ver el detalle persistido de la notificación." />
              )}
            </div>
          </div>
        )}
      </Section>
    </AppShell>
  );
}

function SystemPage() {
  const healthQuery = useQuery({
    queryKey: ["dashboard-system-health"],
    queryFn: getSystemHealth,
  });
  const jobsQuery = useQuery({
    queryKey: ["dashboard-system-jobs"],
    queryFn: getSystemJobs,
  });
  const integrationsQuery = useQuery({
    queryKey: ["dashboard-system-integrations"],
    queryFn: getSystemIntegrations,
  });

  const queryError = healthQuery.isError
    ? healthQuery.error
    : jobsQuery.isError
      ? jobsQuery.error
      : integrationsQuery.isError
        ? integrationsQuery.error
        : null;

  if (healthQuery.isLoading || jobsQuery.isLoading || integrationsQuery.isLoading) {
    return (
      <AppShell title="System" subtitle="Health, jobs recientes e integraciones derivadas honestamente del backend.">
        <SkeletonBlock height={220} />
        <SkeletonBlock height={280} />
        <SkeletonBlock height={280} />
      </AppShell>
    );
  }

  if (queryError) {
    return (
      <AppShell title="System" subtitle="Health, jobs recientes e integraciones derivadas honestamente del backend.">
        <StateScreen title="No pude cargar system" body={queryError.message} tone="bad" />
      </AppShell>
    );
  }

  const health = healthQuery.data as SystemHealthResponse;
  const jobs = ((jobsQuery.data as SystemJobsResponse | undefined)?.items || []);
  const integrations = ((integrationsQuery.data as SystemIntegrationsResponse | undefined)?.items || []);

  return (
    <AppShell title="System" subtitle="Health, jobs recientes e integraciones derivadas honestamente del backend.">
      <Section title="Service health" eyebrow="Honest probes" stagger={0}>
        <HealthSummaryGrid data={health} />
      </Section>

      <div className="dashboard-grid">
        <Section title="Jobs" eyebrow="Recent signals" stagger={1}>
          {jobs.length === 0 ? (
            <StateScreen title="Sin jobs observados" body="Todavía no hay señales suficientes para construir jobs recientes." />
          ) : (
            <div className="stack-list">
              {jobs.map((job, index) => (
                <article className="list-card reveal" key={job.key} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <h4>{job.label}</h4>
                    <StatusChip value={job.status} live={job.status === "ok"} />
                  </div>
                  <p>{job.note || "No note"}</p>
                  <KeyValueList
                    items={[
                      { label: "last run", value: formatDateTime(job.last_run_at) },
                      { label: "last success", value: formatDateTime(job.last_success_at) },
                      { label: "signal source", value: job.signal_source },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Integrations" eyebrow="Derived status" stagger={2}>
          {integrations.length === 0 ? (
            <StateScreen title="Sin integraciones observadas" body="No hay señales suficientes para construir integraciones profundas todavía." />
          ) : (
            <div className="stack-list">
              {integrations.map((integration, index) => (
                <article className="list-card reveal" key={integration.key} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <h4>{integration.label}</h4>
                    <StatusChip value={integration.status} live={integration.status === "ok"} />
                  </div>
                  <p>{integration.note || "No note"}</p>
                  <KeyValueList
                    items={[
                      { label: "last activity", value: formatDateTime(integration.last_activity_at) },
                      { label: "last success", value: formatDateTime(integration.last_success_at) },
                      { label: "signal source", value: integration.signal_source },
                    ]}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>
    </AppShell>
  );
}

function ActivityFeedPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = pickActivityFilters(searchParams);
  const deferredFilters = useDeferredValue(filters);
  const feedQuery = useQuery({
    queryKey: ["dashboard-activity-feed", deferredFilters],
    queryFn: () => getActivityFeed(deferredFilters),
  });
  const feed = feedQuery.data as ActivityFeedResponse | undefined;
  const items = feed?.items || [];
  const [selectedActivityKey, setSelectedActivityKey] = useState<string | null>(null);
  const [savedViews, setSavedViews] = useState<ActivitySavedView[]>([]);
  const [saveViewOpen, setSaveViewOpen] = useState(false);
  const [viewName, setViewName] = useState("");
  const [viewFeedback, setViewFeedback] = useState<string | null>(null);
  const [viewError, setViewError] = useState<string | null>(null);
  const currentQueryString = normalizeActivityQueryString(filters);
  const activeSavedView = savedViews.find((view) => view.queryString === currentQueryString) || null;

  useEffect(() => {
    setSavedViews(readActivitySavedViews());
  }, []);

  useEffect(() => {
    if (!items.length) {
      if (selectedActivityKey !== null) {
        setSelectedActivityKey(null);
      }
      return;
    }
    if (!selectedActivityKey || !items.some((item) => `${item.kind}:${item.id}` === selectedActivityKey)) {
      const firstItem = items[0];
      if (firstItem) {
        setSelectedActivityKey(`${firstItem.kind}:${firstItem.id}`);
      }
    }
  }, [items, selectedActivityKey]);

  const selectedItem = items.find((item) => `${item.kind}:${item.id}` === selectedActivityKey) || null;
  const hasFilters = Object.values(filters).some(Boolean);

  function updateFilter(key: keyof typeof filters, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    setViewFeedback(null);
    setViewError(null);
    setSearchParams(next, { replace: true });
  }

  function clearFilters() {
    const next = new URLSearchParams(searchParams);
    activityFilterKeys.forEach((key) => next.delete(key));
    setViewFeedback(null);
    setViewError(null);
    setSearchParams(next, { replace: true });
  }

  function persistSavedViews(nextViews: ActivitySavedView[]) {
    setSavedViews(nextViews);
    writeActivitySavedViews(nextViews);
  }

  function handleSaveView() {
    const trimmedName = viewName.trim();
    if (!trimmedName) {
      setViewError("Poné un nombre corto para la view.");
      setViewFeedback(null);
      return;
    }
    if (!currentQueryString) {
      setViewError("Primero definí al menos un filtro para guardar una view.");
      setViewFeedback(null);
      return;
    }

    const nextView: ActivitySavedView = {
      id: activeSavedView?.id || `activity-view-${Date.now()}`,
      name: trimmedName,
      filters: { ...filters },
      queryString: currentQueryString,
      createdAt: activeSavedView?.createdAt || new Date().toISOString(),
    };
    const existingIndex = savedViews.findIndex(
      (view) => view.id === nextView.id || view.name.toLowerCase() === trimmedName.toLowerCase(),
    );
    const nextViews = [...savedViews];
    if (existingIndex >= 0) {
      nextViews[existingIndex] = nextView;
      setViewFeedback("Saved view actualizada.");
    } else {
      nextViews.unshift(nextView);
      setViewFeedback("Saved view guardada.");
    }
    persistSavedViews(nextViews);
    setViewError(null);
    setSaveViewOpen(false);
    setViewName("");
  }

  function handleLoadView(view: ActivitySavedView) {
    setViewFeedback(`View cargada: ${view.name}`);
    setViewError(null);
    setSearchParams(new URLSearchParams(view.queryString), { replace: false });
  }

  function handleDeleteView(viewId: string) {
    const nextViews = savedViews.filter((view) => view.id !== viewId);
    persistSavedViews(nextViews);
    setViewFeedback("Saved view eliminada.");
    setViewError(null);
  }

  if (feedQuery.isLoading) {
    return (
      <AppShell title="Activity" subtitle="Feed consolidado construido solo con señales reales persistidas en Ashrise.">
        <SkeletonBlock height={220} />
        <SkeletonBlock height={520} />
      </AppShell>
    );
  }

  if (feedQuery.isError || !feed) {
    return (
      <AppShell title="Activity" subtitle="Feed consolidado construido solo con señales reales persistidas en Ashrise.">
        <StateScreen
          title="No pude cargar activity"
          body={feedQuery.isError ? feedQuery.error.message : "Missing activity payload"}
          tone="bad"
        />
      </AppShell>
    );
  }

  const counts = {
    visible: items.length,
    runs: items.filter((item) => item.kind === "run").length,
    decisions: items.filter((item) => item.kind === "decision").length,
    research: items.filter((item) => item.kind === "research_report").length,
    notifications: items.filter((item) => item.kind === "notification").length,
  };

  return (
    <AppShell
      title="Activity"
      subtitle="Un solo feed read-only para runs, handoffs, decisions, audits, ideas, tasks, research reports y notification events reales."
    >
      <div className="kpi-grid langfuse-kpis">
        <KpiCard label="Visible items" value={counts.visible} note="filtrados y ordenados por timestamp real" stagger={0} />
        <KpiCard label="Runs" value={counts.runs} note="ejecuciones recientes del sistema" stagger={1} />
        <KpiCard label="Decisions" value={counts.decisions} note="cambios explícitos de criterio o alcance" stagger={2} />
        <KpiCard label="Research" value={counts.research} note="candidate research reports persistidos" stagger={3} />
        <KpiCard label="Notifications" value={counts.notifications} note="eventos persistidos del runtime" stagger={4} />
      </div>

      <Section
        title="Activity feed"
        eyebrow="Read-only consolidated view"
        stagger={1}
        aside={
          <div className="saved-views-actions">
            <button className="secondary-button" type="button" onClick={() => setSaveViewOpen((current) => !current)}>
              {saveViewOpen ? "Close save" : "Save view"}
            </button>
            {hasFilters ? (
              <button className="secondary-button" type="button" onClick={clearFilters}>
                Clear filters
              </button>
            ) : null}
            <span className="meta-pill">{items.length} rows</span>
          </div>
        }
      >
        <div className="saved-views-shell">
          <div className="saved-views-copy">
            <div className="eyebrow">Saved views</div>
            <p className="muted-copy">Persistidas en este browser con `localStorage`, para volver rápido a combinaciones útiles de filtros.</p>
          </div>

          {viewError ? <p className="form-error">{viewError}</p> : null}
          {viewFeedback ? <p className="form-success">{viewFeedback}</p> : null}

          {saveViewOpen ? (
            <div className="saved-view-form">
              <input
                value={viewName}
                onChange={(event) => setViewName(event.target.value)}
                placeholder="Nombre de la view"
              />
              <button className="primary-button" type="button" onClick={handleSaveView}>
                Save
              </button>
              <button className="secondary-button" type="button" onClick={() => {
                setSaveViewOpen(false);
                setViewError(null);
              }}>
                Cancel
              </button>
            </div>
          ) : null}

          {savedViews.length === 0 ? (
            <p className="muted-copy">Todavía no guardaste views. Elegí filtros útiles y usá `Save view`.</p>
          ) : (
            <div className="saved-views-list">
              {savedViews.map((view) => {
                const isActive = activeSavedView?.id === view.id;
                return (
                  <article className={`saved-view-card ${isActive ? "active" : ""}`} key={view.id}>
                    <div className="row spread">
                      <div>
                        <h4>{view.name}</h4>
                        <p>{view.queryString ? `?${view.queryString}` : "Sin query string"}</p>
                      </div>
                      {isActive ? <span className="meta-pill">Active</span> : null}
                    </div>
                    <div className="saved-view-actions">
                      <button className="secondary-button" type="button" onClick={() => handleLoadView(view)}>
                        Load
                      </button>
                      <button className="danger-button" type="button" onClick={() => handleDeleteView(view.id)}>
                        Delete
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>

        <div className="filters activity-filters">
          <select value={filters.kind} onChange={(event) => updateFilter("kind", event.target.value)}>
            {activityKindOptions.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            value={filters.project_id}
            onChange={(event) => updateFilter("project_id", event.target.value)}
            placeholder="project_id"
          />
          <input
            value={filters.candidate_id}
            onChange={(event) => updateFilter("candidate_id", event.target.value)}
            placeholder="candidate_id"
          />
          <input
            value={filters.status}
            onChange={(event) => updateFilter("status", event.target.value)}
            placeholder="status"
          />
            <input
              value={filters.source}
              onChange={(event) => updateFilter("source", event.target.value)}
              placeholder="source"
            />
        </div>

        {items.length === 0 ? (
          <StateScreen
            title="No hay actividad para estos filtros"
            body="La estructura está lista y los filtros persisten en la URL; si no hay señales reales para esta combinación, el dashboard muestra vacío honesto."
          />
        ) : (
          <div className="detail-layout">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ts</th>
                    <th>kind</th>
                    <th>title</th>
                    <th>status / verdict</th>
                    <th>actor</th>
                    <th>source</th>
                    <th>subject</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const rowKey = `${item.kind}:${item.id}`;
                    return (
                      <tr
                        key={rowKey}
                        className={rowKey === selectedActivityKey ? "selected-row" : ""}
                        onClick={() => setSelectedActivityKey(rowKey)}
                      >
                        <td>{formatDateTime(item.ts)}</td>
                        <td><span className="meta-pill">{activityKindLabel(item.kind)}</span></td>
                        <td>
                          <strong>{item.title}</strong>
                          <div className="cell-subtitle">{truncateText(item.summary || "Sin summary persistido.", 84)}</div>
                        </td>
                        <td>
                          {item.status ? (
                            <StatusChip value={item.status} live={item.status === "running"} />
                          ) : item.verdict ? (
                            <StatusChip value={item.verdict} />
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>{item.actor || "—"}</td>
                        <td>{item.source || "—"}</td>
                        <td>{activityItemSubject(item)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="detail-panel">
              {selectedItem ? (
                <Section
                  title="Activity detail"
                  eyebrow="Selected event"
                  stagger={2}
                  aside={
                    selectedItem.route ? (
                      <Link className="secondary-button" to={selectedItem.route}>
                        Open source view
                      </Link>
                    ) : undefined
                  }
                >
                  <article className="list-card">
                    <div className="row spread">
                      <h4>{selectedItem.title}</h4>
                      {selectedItem.status ? (
                        <StatusChip value={selectedItem.status} live={selectedItem.status === "running"} />
                      ) : selectedItem.verdict ? (
                        <StatusChip value={selectedItem.verdict} />
                      ) : (
                        <span className="meta-pill">{activityKindLabel(selectedItem.kind)}</span>
                      )}
                    </div>
                    <p>{selectedItem.summary || "Sin summary persistido para este evento."}</p>
                    <KeyValueList
                      items={[
                        { label: "timestamp", value: formatDateTime(selectedItem.ts) },
                        { label: "kind", value: activityKindLabel(selectedItem.kind) },
                        { label: "project", value: selectedItem.project_id || "—" },
                        { label: "candidate", value: selectedItem.candidate_id || "—" },
                        { label: "idea", value: selectedItem.idea_id || "—" },
                        { label: "task", value: selectedItem.task_id || "—" },
                        { label: "run", value: selectedItem.run_id || "—" },
                        { label: "actor", value: selectedItem.actor || "—" },
                        { label: "source", value: selectedItem.source || "—" },
                      ]}
                    />
                  </article>
                  {feed.next_cursor ? (
                    <p className="panel-note">Hay más actividad detrás de esta página. El backend ya expone cursor, aunque esta primera superficie navega solo el bloque reciente.</p>
                  ) : null}
                </Section>
              ) : (
                <StateScreen title="Seleccioná un evento" body="Elegí una fila para ver el detalle lateral del item consolidado." />
              )}
            </div>
          </div>
        )}
      </Section>
    </AppShell>
  );
}

const radarShellItems = [
  { to: "/radar", label: "Overview" },
  { to: "/radar/candidates", label: "Candidates" },
  { to: "/radar/portfolio", label: "Portfolio" },
  { to: "/radar/prompts", label: "Prompts" },
  { to: "/radar/prompt-runs", label: "Prompt Runs" },
  { to: "/radar/import", label: "Import JSON" },
  { to: "/radar/apply-logs", label: "Apply Logs" },
  { to: "/radar/settings", label: "Settings" },
] as const;

const radarStrategyFields = [
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
] as const;

const radarTaxonomyKeys = [...radarStrategyFields] as const;
const radarPortfolioVerdicts = ["KILL", "PARK", "ITERATE", "ADVANCE", "ABSORB"] as const;

const radarCandidateFieldLabels: Record<(typeof radarStrategyFields)[number], string> = {
  focus: "Focus",
  scope: "Scope",
  maturity: "Maturity",
  build_level: "Build level",
  time_horizon: "Time horizon",
  expected_return: "Expected return",
  dominant_risk: "Dominant risk",
  validation_mode: "Validation mode",
  evidence_requirement: "Evidence requirement",
  buyer_type: "Buyer type",
  preferred_channel: "Preferred channel",
  initial_strategy: "Initial strategy",
};

function nullIfBlank(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function slugFromTitle(value: string) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 72);
}

function radarConfigValues(config: RadarConfigItem[] | undefined, key: string) {
  const value = config?.find((item) => item.key === key)?.value;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function jsonFromTextarea(value: string, fallback: Record<string, unknown> = {}) {
  if (!value.trim()) {
    return fallback;
  }
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("El valor debe ser un JSON object.");
  }
  return parsed as Record<string, unknown>;
}

function radarVariableNames(schema: Record<string, unknown> | undefined) {
  if (!schema) {
    return [];
  }
  const properties = schema.properties;
  if (properties && typeof properties === "object" && !Array.isArray(properties)) {
    return Object.keys(properties as Record<string, unknown>);
  }
  return Object.keys(schema).filter((key) => !["type", "required", "description"].includes(key));
}

function RadarShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  const location = useLocation();

  return (
    <AppShell title={title} subtitle={subtitle}>
      <nav className="radar-subnav" aria-label="Radar navigation">
        {radarShellItems.map((item) => {
          const isActive = location.pathname === item.to || (item.to !== "/radar" && location.pathname.startsWith(item.to));
          return (
            <Link className={isActive ? "active" : ""} key={item.to} to={item.to}>
              {item.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </AppShell>
  );
}

function RadarOverviewPage() {
  const candidatesQuery = useQuery({ queryKey: ["radar-candidates"], queryFn: getRadarCandidates });
  const logsQuery = useQuery({ queryKey: ["radar-apply-logs", "overview"], queryFn: () => getRadarApplyLogs({ limit: "8" }) });

  const candidates = candidatesQuery.data || [];
  const logs = logsQuery.data || [];
  const byVerdict = candidates.reduce<Record<string, number>>((acc, item) => {
    const key = item.verdict || "no_verdict";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const byMaturity = candidates.reduce<Record<string, number>>((acc, item) => {
    const key = item.maturity || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const latestLog = logs[0];

  return (
    <RadarShell
      title="Radar"
      subtitle="Workbench manual para discovery: candidates, prompts, evidence, apply logs y JSON import sin watcher todavia."
    >
      <div className="kpi-grid">
        <KpiCard label="Candidates" value={candidates.length} note="radar_candidates totales" stagger={0} />
        <KpiCard label="Verdicts" value={Object.keys(byVerdict).length} note="agrupaciones con verdict" stagger={1} />
        <KpiCard label="Maturity" value={Object.keys(byMaturity).length} note="estados de discovery usados" stagger={2} />
        <KpiCard label="Recent applies" value={logs.length} note={latestLog ? `${latestLog.status} · ${formatDateTime(latestLog.created_at)}` : "sin apply logs"} stagger={3} />
      </div>

      <div className="dashboard-grid">
        <Section title="Quick actions" eyebrow="Manual loop" stagger={1}>
          <div className="hero-actions">
            <Link className="primary-button" to="/radar/candidates?new=1">New Candidate</Link>
            <Link className="secondary-button" to="/radar/import">Import JSON</Link>
            <Link className="secondary-button" to="/radar/prompts">Prompts</Link>
            <Link className="secondary-button" to="/radar/apply-logs">Apply Logs</Link>
          </div>
          <p className="panel-note">Fase 3 mantiene el flujo manual: copiar prompt, ejecutar en ChatGPT Web o Claude Web, pegar/arrastrar JSON y aplicar.</p>
        </Section>

        <Section title="Candidates by verdict" eyebrow="Honest aggregates" stagger={2}>
          {candidatesQuery.isLoading ? (
            <SkeletonBlock height={180} />
          ) : Object.keys(byVerdict).length === 0 ? (
            <StateScreen title="Sin candidates" body="Crea una candidate para empezar a poblar Radar." />
          ) : (
            <div className="stack-list compact">
              {Object.entries(byVerdict).map(([key, count]) => (
                <article className="list-card" key={key}>
                  <div className="row spread">
                    <h4>{key}</h4>
                    <span className="meta-pill">{count}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Recent manual applies" eyebrow="Import history" stagger={3}>
          {logsQuery.isLoading ? (
            <SkeletonBlock height={220} />
          ) : logs.length === 0 ? (
            <StateScreen title="Sin apply logs" body="Cuando hagas dry-run o apply, el historial va a aparecer aca." />
          ) : (
            <div className="stack-list compact">
              {logs.map((item) => (
                <article className="list-card" key={item.id}>
                  <div className="row spread">
                    <h4>{item.model_used || item.recognized_format || "Manual apply"}</h4>
                    <StatusChip value={item.status} />
                  </div>
                  <p>{item.error_message || item.notes || item.candidate_id || "Apply log sin detalle extra."}</p>
                  <div className="meta-row">
                    <span>{item.source_type}</span>
                    <span>{formatDateTime(item.created_at)}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Candidates by maturity" eyebrow="Discovery stage" stagger={4}>
          {Object.keys(byMaturity).length === 0 ? (
            <StateScreen title="Sin maturity" body="Todavia no hay candidates con maturity persistida." />
          ) : (
            <div className="stack-list compact">
              {Object.entries(byMaturity).map(([key, count]) => (
                <article className="list-card" key={key}>
                  <div className="row spread">
                    <h4>{key}</h4>
                    <span className="meta-pill">{count}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>
    </RadarShell>
  );
}

function RadarCandidatesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [newCandidate, setNewCandidate] = useState({ name: "", slug: "", hypothesis: "", focus: "", scope: "", maturity: "candidate" });
  const [filters, setFilters] = useState({
    q: searchParams.get("q") || "",
    verdict: searchParams.get("verdict") || "",
    focus: searchParams.get("focus") || "",
    scope: searchParams.get("scope") || "",
    maturity: searchParams.get("maturity") || "",
    dominant_risk: searchParams.get("dominant_risk") || "",
  });

  const candidatesQuery = useQuery({ queryKey: ["radar-candidates"], queryFn: getRadarCandidates });
  const configQuery = useQuery({ queryKey: ["radar-config"], queryFn: getRadarConfig });
  const createMutation = useMutation({
    mutationFn: () =>
      createRadarCandidate({
        slug: newCandidate.slug || slugFromTitle(newCandidate.name),
        name: newCandidate.name,
        hypothesis: nullIfBlank(newCandidate.hypothesis),
        focus: nullIfBlank(newCandidate.focus),
        scope: nullIfBlank(newCandidate.scope),
        maturity: nullIfBlank(newCandidate.maturity),
      }),
    onSuccess: (candidate) => {
      queryClient.invalidateQueries({ queryKey: ["radar-candidates"] });
      navigate(`/radar/candidates/${candidate.id}`);
    },
  });

  useEffect(() => {
    const next = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) {
        next.set(key, value);
      }
    });
    setSearchParams(next, { replace: true });
  }, [filters, setSearchParams]);

  const candidates = candidatesQuery.data || [];
  const config = configQuery.data || [];
  const q = filters.q.trim().toLowerCase();
  const filteredCandidates = candidates.filter((candidate) => {
    const haystack = [candidate.name, candidate.slug, candidate.summary, candidate.hypothesis].filter(Boolean).join(" ").toLowerCase();
    return (
      (!q || haystack.includes(q)) &&
      (!filters.verdict || candidate.verdict === filters.verdict) &&
      (!filters.focus || candidate.focus === filters.focus) &&
      (!filters.scope || candidate.scope === filters.scope) &&
      (!filters.maturity || candidate.maturity === filters.maturity) &&
      (!filters.dominant_risk || candidate.dominant_risk === filters.dominant_risk)
    );
  });

  return (
    <RadarShell title="Radar Candidates" subtitle="Lista operativa de oportunidades de discovery, separada de vertical_candidates de Ashrise.">
      <Section title="New Candidate" eyebrow="Manual create" stagger={0}>
        <form
          className="radar-form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
        >
          <label>
            Name
            <input value={newCandidate.name} onChange={(event) => setNewCandidate((current) => ({ ...current, name: event.target.value, slug: current.slug || slugFromTitle(event.target.value) }))} required />
          </label>
          <label>
            Slug
            <input value={newCandidate.slug} onChange={(event) => setNewCandidate((current) => ({ ...current, slug: event.target.value }))} required />
          </label>
          <label>
            Focus
            <select value={newCandidate.focus} onChange={(event) => setNewCandidate((current) => ({ ...current, focus: event.target.value }))}>
              <option value="">Sin focus</option>
              {radarConfigValues(config, "focus").map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Scope
            <select value={newCandidate.scope} onChange={(event) => setNewCandidate((current) => ({ ...current, scope: event.target.value }))}>
              <option value="">Sin scope</option>
              {radarConfigValues(config, "scope").map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Maturity
            <select value={newCandidate.maturity} onChange={(event) => setNewCandidate((current) => ({ ...current, maturity: event.target.value }))}>
              {radarConfigValues(config, "maturity").map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="wide-field">
            Hypothesis
            <textarea value={newCandidate.hypothesis} onChange={(event) => setNewCandidate((current) => ({ ...current, hypothesis: event.target.value }))} />
          </label>
          <div className="hero-actions wide-field">
            <button className="primary-button" type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create candidate"}
            </button>
            {createMutation.error instanceof Error ? <span className="form-error">{createMutation.error.message}</span> : null}
          </div>
        </form>
      </Section>

      <Section title="Candidates" eyebrow="Search + filters" stagger={1} aside={<span className="meta-pill">{filteredCandidates.length} / {candidates.length}</span>}>
        <div className="filters">
          <input placeholder="Search name, slug, hypothesis..." value={filters.q} onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))} />
          <input placeholder="verdict" value={filters.verdict} onChange={(event) => setFilters((current) => ({ ...current, verdict: event.target.value }))} />
          {(["focus", "scope", "maturity", "dominant_risk"] as const).map((key) => (
            <select key={key} value={filters[key]} onChange={(event) => setFilters((current) => ({ ...current, [key]: event.target.value }))}>
              <option value="">{radarCandidateFieldLabels[key]}</option>
              {radarConfigValues(config, key).map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          ))}
        </div>

        {candidatesQuery.isLoading ? (
          <SkeletonBlock height={360} />
        ) : filteredCandidates.length === 0 ? (
          <StateScreen title="Sin candidates para estos filtros" body="Ajusta la busqueda o crea una nueva candidate." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Slug</th>
                  <th>Verdict</th>
                  <th>Focus</th>
                  <th>Scope</th>
                  <th>Maturity</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.map((candidate) => (
                  <tr key={candidate.id}>
                    <td><Link to={`/radar/candidates/${candidate.id}`}>{candidate.name}</Link></td>
                    <td>{candidate.slug}</td>
                    <td>{candidate.verdict || "—"}</td>
                    <td>{candidate.focus || "—"}</td>
                    <td>{candidate.scope || "—"}</td>
                    <td>{candidate.maturity || "—"}</td>
                    <td>{formatDateTime(candidate.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </RadarShell>
  );
}

function RadarCountList({ items }: { items: { value: string; count: number }[] }) {
  if (items.length === 0) {
    return <StateScreen title="Sin datos" body="Todavia no hay candidates para agrupar." />;
  }
  return (
    <div className="stack-list compact">
      {items.map((item) => (
        <article className="list-card" key={item.value}>
          <div className="row spread">
            <h4>{item.value}</h4>
            <span className="meta-pill">{item.count}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function RadarMatrixTable({ matrix }: { matrix: RadarPortfolioMatrix }) {
  if (matrix.rows.length === 0 || matrix.columns.length === 0) {
    return <StateScreen title="Matriz vacia" body="Todavia no hay candidates suficientes para esta matriz." />;
  }
  const cellFor = (row: string, column: string) => matrix.cells.find((cell) => cell.row === row && cell.column === column);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>dimension</th>
            {matrix.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row) => (
            <tr key={row}>
              <td><strong>{row}</strong></td>
              {matrix.columns.map((column) => {
                const cell = cellFor(row, column);
                return (
                  <td key={`${row}-${column}`}>
                    <span className="meta-pill">{cell?.count || 0}</span>
                    {cell?.candidates.length ? <div className="cell-subtitle">{cell.candidates.slice(0, 3).map((item) => item.slug).join(", ")}</div> : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RadarPortfolioCandidateTable({ candidates, showReasons = false }: { candidates: (RadarPortfolioCandidate & { reasons?: string[] })[]; showReasons?: boolean }) {
  if (candidates.length === 0) {
    return <StateScreen title="Sin candidates" body="No hay candidates para esta seccion." />;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>name</th>
            <th>verdict</th>
            <th>maturity</th>
            <th>focus</th>
            <th>scope</th>
            <th>risk</th>
            <th>promotion</th>
            <th>evidence</th>
            <th>updated</th>
            <th>action</th>
            {showReasons ? <th>reasons</th> : null}
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.id}>
              <td>
                <Link className="cell-title" to={`/radar/candidates/${candidate.id}`}>{candidate.name}</Link>
                <div className="cell-subtitle">{candidate.slug}</div>
              </td>
              <td>{candidate.verdict ? <StatusChip value={candidate.verdict} /> : "—"}</td>
              <td>{candidate.maturity || "—"}</td>
              <td>{candidate.focus || "—"}</td>
              <td>{candidate.scope || "—"}</td>
              <td>{candidate.dominant_risk || "—"}</td>
              <td>
                {candidate.promoted_link_count > 0 ? (
                  <span className="meta-pill">Promoted {candidate.promoted_target_slug || candidate.promoted_target_id}</span>
                ) : (
                  "—"
                )}
              </td>
              <td>{candidate.evidence_count}</td>
              <td>{formatDateTime(candidate.updated_at)}</td>
              <td><Link to={`/radar/candidates/${candidate.id}`}>Promote</Link></td>
              {showReasons ? <td>{candidate.reasons?.join(", ") || "—"}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RadarPortfolioPage() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const overviewQuery = useQuery({ queryKey: ["radar-portfolio-overview"], queryFn: getRadarPortfolioOverview });
  const focusScopeQuery = useQuery({ queryKey: ["radar-portfolio-focus-scope"], queryFn: getRadarPortfolioFocusScopeMatrix });
  const maturityVerdictQuery = useQuery({ queryKey: ["radar-portfolio-maturity-verdict"], queryFn: getRadarPortfolioMaturityVerdictMatrix });
  const riskQuery = useQuery({ queryKey: ["radar-portfolio-risk"], queryFn: getRadarPortfolioRiskDistribution });
  const queueQuery = useQuery({ queryKey: ["radar-portfolio-selection-queue"], queryFn: getRadarPortfolioSelectionQueue });
  const candidatesQuery = useQuery({ queryKey: ["radar-candidates"], queryFn: getRadarCandidates });
  const compareMutation = useMutation({ mutationFn: () => compareRadarPortfolioCandidates(selectedIds) });

  const overview = overviewQuery.data;
  const candidates = candidatesQuery.data || [];
  const compared = compareMutation.data?.items || [];
  const isLoading = overviewQuery.isLoading || focusScopeQuery.isLoading || maturityVerdictQuery.isLoading || riskQuery.isLoading || queueQuery.isLoading;
  const error =
    overviewQuery.error ||
    focusScopeQuery.error ||
    maturityVerdictQuery.error ||
    riskQuery.error ||
    queueQuery.error;

  function toggleCompare(candidateId: string) {
    setSelectedIds((current) =>
      current.includes(candidateId)
        ? current.filter((item) => item !== candidateId)
        : current.length < 8
          ? [...current, candidateId]
          : current,
    );
  }

  return (
    <RadarShell title="Radar Portfolio" subtitle="Review minimo para comparar candidatas y decidir kill, park, iterate, advance o absorb.">
      {isLoading ? (
        <SkeletonBlock height={540} />
      ) : error || !overview ? (
        <StateScreen title="No pude cargar portfolio" body={error instanceof Error ? error.message : "Portfolio no disponible."} tone="bad" />
      ) : (
        <div className="dashboard-grid">
          <div className="kpi-grid">
            <KpiCard label="Total candidates" value={overview.total_candidates} note="Radar discovery portfolio" stagger={0} />
            <KpiCard label="Without verdict" value={overview.candidates_without_verdict.length} note="requieren decision" stagger={1} live={overview.candidates_without_verdict.length > 0} />
            <KpiCard label="Without evidence" value={overview.candidates_without_evidence.length} note="evidence_count = 0" stagger={2} />
            <KpiCard label="Failed gates" value={overview.candidates_with_failed_gates.length} note="gates false/weak/red" stagger={3} />
          </div>

          <Section title="Focus x Scope" eyebrow="Matrix" stagger={1}>
            {focusScopeQuery.data ? <RadarMatrixTable matrix={focusScopeQuery.data} /> : null}
          </Section>

          <Section title="Maturity x Verdict" eyebrow="Matrix" stagger={2}>
            {maturityVerdictQuery.data ? <RadarMatrixTable matrix={maturityVerdictQuery.data} /> : null}
          </Section>

          <Section title="Risk distribution" eyebrow="Dominant risk" stagger={3}>
            <div className="stack-list compact">
              {(riskQuery.data || []).map((item) => (
                <article className="list-card" key={item.dominant_risk}>
                  <div className="row spread">
                    <h4>{item.dominant_risk}</h4>
                    <span className="meta-pill">{item.count}</span>
                  </div>
                  <p>{item.candidates.slice(0, 4).map((candidate) => candidate.slug).join(", ") || "Sin candidates."}</p>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Selection Queue" eyebrow="Needs decision" stagger={4} aside={<span className="meta-pill">{queueQuery.data?.length || 0}</span>}>
            <RadarPortfolioCandidateTable candidates={queueQuery.data || []} showReasons />
          </Section>

          <Section title="Compare candidates" eyebrow="Side by side" stagger={5}>
            <div className="filters">
              <select
                value=""
                onChange={(event) => {
                  if (event.target.value) {
                    toggleCompare(event.target.value);
                  }
                }}
              >
                <option value="">Agregar candidate a compare</option>
                {candidates.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>{candidate.name}</option>
                ))}
              </select>
              <button className="primary-button" type="button" disabled={selectedIds.length === 0 || compareMutation.isPending} onClick={() => compareMutation.mutate()}>
                {compareMutation.isPending ? "Comparing..." : "Compare"}
              </button>
            </div>
            <div className="meta-row">
              {selectedIds.map((candidateId) => {
                const candidate = candidates.find((item) => item.id === candidateId);
                return (
                  <button className="meta-pill" key={candidateId} type="button" onClick={() => toggleCompare(candidateId)}>
                    {candidate?.slug || candidateId} x
                  </button>
                );
              })}
            </div>
            {compareMutation.error instanceof Error ? <p className="form-error">{compareMutation.error.message}</p> : null}
            {compared.length ? <RadarPortfolioCandidateTable candidates={compared} /> : <StateScreen title="Sin comparacion" body="Elegí 2 o mas candidates para compararlas en tabla simple." />}
          </Section>

          <Section title="Verdict counts" eyebrow="Distribution" stagger={6}>
            <RadarCountList items={overview.count_by_verdict} />
          </Section>
        </div>
      )}
    </RadarShell>
  );
}

function RadarCandidateDetailPage() {
  const { candidateId = "" } = useParams();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [evidenceForm, setEvidenceForm] = useState({ kind: "web_note", title: "", claim: "", url: "", source_name: "", confidence: "" });
  const [promotionNotes, setPromotionNotes] = useState("");
  const [promotionOverride, setPromotionOverride] = useState(false);
  const [promotionForce, setPromotionForce] = useState(false);
  const [promotionCreateDecision, setPromotionCreateDecision] = useState(false);

  const candidateQuery = useQuery({ queryKey: ["radar-candidate", candidateId], queryFn: () => getRadarCandidate(candidateId), enabled: Boolean(candidateId) });
  const evidenceQuery = useQuery({ queryKey: ["radar-evidence", candidateId], queryFn: () => getRadarCandidateEvidence(candidateId), enabled: Boolean(candidateId) });
  const logsQuery = useQuery({ queryKey: ["radar-apply-logs", candidateId], queryFn: () => getRadarApplyLogs({ candidate_id: candidateId, limit: "8" }), enabled: Boolean(candidateId) });
  const configQuery = useQuery({ queryKey: ["radar-config"], queryFn: getRadarConfig });
  const linksQuery = useQuery({ queryKey: ["radar-candidate-links", candidateId], queryFn: () => getRadarCandidateLinks(candidateId), enabled: Boolean(candidateId) });

  const candidate = candidateQuery.data;
  const evidence = evidenceQuery.data || [];
  const logs = logsQuery.data || [];
  const config = configQuery.data || [];
  const links = linksQuery.data || [];
  const promotedLink = links.find((link) => link.target_type === "vertical_candidate" && link.relation_type === "promoted_to") || null;

  useEffect(() => {
    if (!candidate) {
      return;
    }
    setForm({
      name: candidate.name || "",
      slug: candidate.slug || "",
      summary: candidate.summary || "",
      hypothesis: candidate.hypothesis || "",
      verdict: candidate.verdict || "",
      priority: candidate.priority === null ? "" : String(candidate.priority),
      notes: candidate.notes || "",
      decision_memo: candidate.decision_memo || "",
      ...Object.fromEntries(radarStrategyFields.map((field) => [field, candidate[field] || ""])),
    });
  }, [candidate]);

  const updateMutation = useMutation({
    mutationFn: () =>
      updateRadarCandidate(candidateId, {
        name: form.name,
        slug: form.slug,
        summary: nullIfBlank(form.summary || ""),
        hypothesis: nullIfBlank(form.hypothesis || ""),
        verdict: nullIfBlank(form.verdict || ""),
        priority: form.priority ? Number(form.priority) : null,
        notes: nullIfBlank(form.notes || ""),
        decision_memo: nullIfBlank(form.decision_memo || ""),
        ...Object.fromEntries(radarStrategyFields.map((field) => [field, nullIfBlank(form[field] || "")])),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["radar-candidate", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["radar-candidates"] });
    },
  });

  const quickVerdictMutation = useMutation({
    mutationFn: (verdict: string) => updateRadarCandidate(candidateId, { verdict }),
    onSuccess: (updatedCandidate) => {
      setForm((current) => ({ ...current, verdict: updatedCandidate.verdict || "" }));
      queryClient.invalidateQueries({ queryKey: ["radar-candidate", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["radar-candidates"] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-overview"] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-focus-scope"] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-maturity-verdict"] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-risk"] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-selection-queue"] });
    },
  });

  const createEvidenceMutation = useMutation({
    mutationFn: () =>
      createRadarCandidateEvidence(candidateId, {
        kind: evidenceForm.kind,
        title: nullIfBlank(evidenceForm.title),
        claim: nullIfBlank(evidenceForm.claim),
        url: nullIfBlank(evidenceForm.url),
        source_name: nullIfBlank(evidenceForm.source_name),
        confidence: evidenceForm.confidence ? Number(evidenceForm.confidence) : null,
      }),
    onSuccess: () => {
      setEvidenceForm({ kind: "web_note", title: "", claim: "", url: "", source_name: "", confidence: "" });
      queryClient.invalidateQueries({ queryKey: ["radar-evidence", candidateId] });
    },
  });

  const deleteEvidenceMutation = useMutation({
    mutationFn: deleteRadarEvidence,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["radar-evidence", candidateId] }),
  });

  const promotionPreviewMutation = useMutation<RadarPromotionPreview, Error>({
    mutationFn: () => getRadarPromotionPreview(candidateId),
  });

  const promotionMutation = useMutation({
    mutationFn: () =>
      promoteRadarCandidate(candidateId, {
        target_type: "vertical_candidate",
        confirm: true,
        notes: nullIfBlank(promotionNotes),
        create_decision: promotionCreateDecision,
        force: promotionForce,
        override_verdict: promotionOverride,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["radar-candidate-links", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-overview"] });
      queryClient.invalidateQueries({ queryKey: ["radar-portfolio-selection-queue"] });
      queryClient.invalidateQueries({ queryKey: ["radar-candidates"] });
      promotionPreviewMutation.mutate();
    },
  });

  function handleConfirmPromotion() {
    if (!promotionPreviewMutation.data) {
      return;
    }
    if (!window.confirm("Promote this Radar candidate to an Ashrise vertical_candidate? This will create an explicit link but will not create a project.")) {
      return;
    }
    promotionMutation.mutate();
  }

  if (candidateQuery.isLoading) {
    return (
      <RadarShell title="Radar Candidate" subtitle="Detalle de candidate Radar.">
        <SkeletonBlock height={540} />
      </RadarShell>
    );
  }

  if (candidateQuery.isError || !candidate) {
    return (
      <RadarShell title="Radar Candidate" subtitle="Detalle de candidate Radar.">
        <StateScreen title="Candidate no encontrada" body={candidateQuery.error?.message || "No pude cargar esta candidate."} tone="bad" />
      </RadarShell>
    );
  }

  return (
    <RadarShell title={candidate.name} subtitle="Summary, strategy, evaluation, evidence y apply logs de discovery.">
      <div className="dashboard-grid">
        <Section title="Summary + Strategy" eyebrow={candidate.slug} stagger={0}>
          <div className="list-card">
            <div className="row spread">
              <div>
                <div className="eyebrow">Portfolio decision</div>
                <p className="muted-copy">Set verdict rapido para revisar el portfolio sin promocionar automaticamente.</p>
              </div>
              <StatusChip value={form.verdict || "without verdict"} />
            </div>
            <div className="hero-actions">
              {radarPortfolioVerdicts.map((verdict) => (
                <button
                  className={form.verdict === verdict ? "primary-button" : "secondary-button"}
                  disabled={quickVerdictMutation.isPending}
                  key={verdict}
                  onClick={() => quickVerdictMutation.mutate(verdict)}
                  type="button"
                >
                  Set {verdict}
                </button>
              ))}
            </div>
            {quickVerdictMutation.isSuccess ? <p className="form-success">Verdict actualizado.</p> : null}
            {quickVerdictMutation.error instanceof Error ? <p className="form-error">{quickVerdictMutation.error.message}</p> : null}
          </div>
          <form
            className="radar-form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              updateMutation.mutate();
            }}
          >
            <label>Name<input value={form.name || ""} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
            <label>Slug<input value={form.slug || ""} onChange={(event) => setForm((current) => ({ ...current, slug: event.target.value }))} required /></label>
            <label>Verdict<input value={form.verdict || ""} onChange={(event) => setForm((current) => ({ ...current, verdict: event.target.value }))} placeholder="kill / iterate / advance" /></label>
            <label>Priority<input type="number" min="0" value={form.priority || ""} onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value }))} /></label>
            <label className="wide-field">Summary<textarea value={form.summary || ""} onChange={(event) => setForm((current) => ({ ...current, summary: event.target.value }))} /></label>
            <label className="wide-field">Hypothesis<textarea value={form.hypothesis || ""} onChange={(event) => setForm((current) => ({ ...current, hypothesis: event.target.value }))} /></label>
            {radarStrategyFields.map((field) => (
              <label key={field}>
                {radarCandidateFieldLabels[field]}
                <select value={form[field] || ""} onChange={(event) => setForm((current) => ({ ...current, [field]: event.target.value }))}>
                  <option value="">Sin valor</option>
                  {radarConfigValues(config, field).map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
            ))}
            <label className="wide-field">Notes<textarea value={form.notes || ""} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} /></label>
            <div className="hero-actions wide-field">
              <button className="primary-button" type="submit" disabled={updateMutation.isPending}>{updateMutation.isPending ? "Saving..." : "Save candidate"}</button>
              <Link className="secondary-button" to={`/radar/import?candidate_id=${candidate.id}`}>Import JSON for this candidate</Link>
              {updateMutation.isSuccess ? <span className="form-success">Saved.</span> : null}
              {updateMutation.error instanceof Error ? <span className="form-error">{updateMutation.error.message}</span> : null}
            </div>
          </form>
        </Section>

        <Section title="Promotion to Ashrise" eyebrow="Explicit bridge" stagger={1}>
          <div className="stack-list">
            <article className="list-card">
              <div className="row spread">
                <div>
                  <h4>{promotedLink ? "Promoted" : "Not promoted yet"}</h4>
                  <p className="muted-copy">Promotion creates an Ashrise vertical_candidate and a Radar link. It does not create a project automatically.</p>
                </div>
                <StatusChip value={promotedLink ? "promoted" : "manual"} />
              </div>
              {linksQuery.isLoading ? (
                <SkeletonBlock height={80} />
              ) : links.length === 0 ? (
                <p className="muted-copy">No links yet.</p>
              ) : (
                <div className="stack-list compact">
                  {links.map((link: RadarCandidateLink) => (
                    <article className="list-card" key={link.id}>
                      <div className="row spread">
                        <div>
                          <h4>{link.target_slug || link.target_id}</h4>
                          <p>{link.relation_type} / {link.target_type}</p>
                        </div>
                        <span className="meta-pill">{formatDateTime(link.created_at)}</span>
                      </div>
                      {link.notes ? <p>{link.notes}</p> : null}
                    </article>
                  ))}
                </div>
              )}
            </article>

            <article className="list-card">
              <div className="hero-actions">
                <button className="secondary-button" type="button" disabled={promotionPreviewMutation.isPending} onClick={() => promotionPreviewMutation.mutate()}>
                  {promotionPreviewMutation.isPending ? "Previewing..." : "Preview promotion"}
                </button>
              </div>
              {promotionPreviewMutation.error instanceof Error ? <p className="form-error">{promotionPreviewMutation.error.message}</p> : null}
              {promotionPreviewMutation.data ? (
                <div className="json-block-group">
                  <div>
                    <span className="eyebrow">warnings</span>
                    {promotionPreviewMutation.data.warnings.length === 0 ? (
                      <p className="form-success">No warnings.</p>
                    ) : (
                      <ul className="compact-list">
                        {promotionPreviewMutation.data.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                      </ul>
                    )}
                  </div>
                  <div>
                    <span className="eyebrow">suggested vertical_candidate payload</span>
                    <pre className="json-block">{prettyJson(promotionPreviewMutation.data.suggested_payload)}</pre>
                  </div>
                </div>
              ) : null}
            </article>

            <article className="list-card">
              <label>
                Promotion notes
                <textarea value={promotionNotes} onChange={(event) => setPromotionNotes(event.target.value)} placeholder="Why this candidate is entering Ashrise." />
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={promotionCreateDecision} onChange={(event) => setPromotionCreateDecision(event.target.checked)} />
                Request decision logging if a project context exists
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={promotionOverride} onChange={(event) => setPromotionOverride(event.target.checked)} />
                Override non-ADVANCE verdict
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={promotionForce} onChange={(event) => setPromotionForce(event.target.checked)} />
                Force a new promotion if a link already exists
              </label>
              <div className="hero-actions">
                <button className="primary-button" type="button" disabled={!promotionPreviewMutation.data || promotionMutation.isPending} onClick={handleConfirmPromotion}>
                  {promotionMutation.isPending ? "Promoting..." : "Confirm Promote"}
                </button>
              </div>
              {promotionMutation.data ? (
                <p className="form-success">Promoted to {promotionMutation.data.target_slug || promotionMutation.data.target_id}.</p>
              ) : null}
              {promotionMutation.error instanceof Error ? <p className="form-error">{promotionMutation.error.message}</p> : null}
            </article>
          </div>
        </Section>

        <Section title="Evaluation" eyebrow="Applied JSON state" stagger={1}>
          <label>
            Decision memo
            <textarea value={form.decision_memo || ""} onChange={(event) => setForm((current) => ({ ...current, decision_memo: event.target.value }))} />
          </label>
          <div className="json-block-group">
            <div><span className="eyebrow">scorecard</span><pre className="json-block">{prettyJson(candidate.scorecard)}</pre></div>
            <div><span className="eyebrow">gates</span><pre className="json-block">{prettyJson(candidate.gates)}</pre></div>
            <div><span className="eyebrow">next_research</span><pre className="json-block">{prettyJson(candidate.next_research)}</pre></div>
            <div><span className="eyebrow">kill_criteria</span><pre className="json-block">{prettyJson(candidate.kill_criteria)}</pre></div>
          </div>
        </Section>

        <Section title="Evidence" eyebrow="Manual + imported" stagger={2} aside={<span className="meta-pill">{evidence.length}</span>}>
          <form
            className="radar-form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              createEvidenceMutation.mutate();
            }}
          >
            <label>Kind<input value={evidenceForm.kind} onChange={(event) => setEvidenceForm((current) => ({ ...current, kind: event.target.value }))} required /></label>
            <label>Title<input value={evidenceForm.title} onChange={(event) => setEvidenceForm((current) => ({ ...current, title: event.target.value }))} /></label>
            <label>URL<input value={evidenceForm.url} onChange={(event) => setEvidenceForm((current) => ({ ...current, url: event.target.value }))} /></label>
            <label>Source<input value={evidenceForm.source_name} onChange={(event) => setEvidenceForm((current) => ({ ...current, source_name: event.target.value }))} /></label>
            <label>Confidence<input type="number" min="0" max="1" step="0.05" value={evidenceForm.confidence} onChange={(event) => setEvidenceForm((current) => ({ ...current, confidence: event.target.value }))} /></label>
            <label className="wide-field">Claim<textarea value={evidenceForm.claim} onChange={(event) => setEvidenceForm((current) => ({ ...current, claim: event.target.value }))} /></label>
            <div className="hero-actions wide-field"><button className="secondary-button" type="submit" disabled={createEvidenceMutation.isPending}>Add Evidence</button></div>
          </form>
          {evidenceQuery.isLoading ? (
            <SkeletonBlock height={180} />
          ) : evidence.length === 0 ? (
            <StateScreen title="Sin evidence" body="Aca va a aparecer evidence importada o agregada manualmente." />
          ) : (
            <div className="stack-list compact">
              {evidence.map((item) => (
                <article className="list-card" key={item.id}>
                  <div className="row spread">
                    <h4>{item.title || item.kind}</h4>
                    <button className="ghost-button" type="button" onClick={() => deleteEvidenceMutation.mutate(item.id)}>Delete</button>
                  </div>
                  <p>{item.claim || item.notes || "Sin claim."}</p>
                  <div className="meta-row">
                    <span>{item.source_name || "source n/a"}</span>
                    <span>{item.confidence !== null ? `confidence ${item.confidence}` : "sin confidence"}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Apply Logs" eyebrow="Candidate scoped" stagger={3} aside={<span className="meta-pill">{logs.length}</span>}>
          {logsQuery.isLoading ? (
            <SkeletonBlock height={180} />
          ) : logs.length === 0 ? (
            <StateScreen title="Sin apply logs" body="Todavia no hay dry-runs ni applies asociados a esta candidate." />
          ) : (
            <div className="stack-list compact">
              {logs.map((item) => (
                <article className="list-card" key={item.id}>
                  <div className="row spread">
                    <h4>{item.model_used || item.recognized_format || "Apply"}</h4>
                    <StatusChip value={item.status} />
                  </div>
                  <p>{item.error_message || item.notes || "Sin error."}</p>
                  <div className="meta-row"><span>{item.source_type}</span><span>{formatDateTime(item.created_at)}</span></div>
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>
    </RadarShell>
  );
}

function RadarPromptsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({ q: "", prompt_type: "", active: "" });
  const [newPrompt, setNewPrompt] = useState({ key: "", title: "", prompt_type: "discovery", description: "" });
  const promptsQuery = useQuery({ queryKey: ["radar-prompts"], queryFn: getRadarPrompts });
  const createMutation = useMutation({
    mutationFn: () =>
      createRadarPrompt({
        key: newPrompt.key || slugFromTitle(newPrompt.title),
        title: newPrompt.title,
        prompt_type: newPrompt.prompt_type,
        description: nullIfBlank(newPrompt.description),
      }),
    onSuccess: (prompt) => {
      queryClient.invalidateQueries({ queryKey: ["radar-prompts"] });
      navigate(`/radar/prompts/${prompt.id}`);
    },
  });

  const prompts = promptsQuery.data || [];
  const promptTypes = Array.from(new Set(prompts.map((item) => item.prompt_type))).sort();
  const q = filters.q.trim().toLowerCase();
  const filteredPrompts = prompts.filter((prompt) => {
    const tags = Array.isArray(prompt.metadata?.tags) ? prompt.metadata.tags.join(" ") : "";
    const activeMatches =
      !filters.active ||
      (filters.active === "active" ? prompt.latest_version_is_active === true : prompt.latest_version_is_active !== true);
    return (
      (!q || [prompt.key, prompt.title, prompt.description, tags].filter(Boolean).join(" ").toLowerCase().includes(q)) &&
      (!filters.prompt_type || prompt.prompt_type === filters.prompt_type) &&
      activeMatches
    );
  });

  return (
    <RadarShell title="Radar Prompts" subtitle="Biblioteca practica para copiar prompts y ejecutar fuera de API en ChatGPT Web o Claude Web.">
      <Section title="New Prompt" eyebrow="Prompt library" stagger={0}>
        <form
          className="radar-form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
        >
          <label>Title<input value={newPrompt.title} onChange={(event) => setNewPrompt((current) => ({ ...current, title: event.target.value, key: current.key || slugFromTitle(event.target.value) }))} required /></label>
          <label>Key<input value={newPrompt.key} onChange={(event) => setNewPrompt((current) => ({ ...current, key: event.target.value }))} required /></label>
          <label>Type<input value={newPrompt.prompt_type} onChange={(event) => setNewPrompt((current) => ({ ...current, prompt_type: event.target.value }))} required /></label>
          <label className="wide-field">Description<textarea value={newPrompt.description} onChange={(event) => setNewPrompt((current) => ({ ...current, description: event.target.value }))} /></label>
          <div className="hero-actions wide-field">
            <button className="primary-button" type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? "Creating..." : "Create prompt"}</button>
            {createMutation.error instanceof Error ? <span className="form-error">{createMutation.error.message}</span> : null}
          </div>
        </form>
      </Section>

      <Section title="Prompts" eyebrow="Search + filters" stagger={1} aside={<span className="meta-pill">{filteredPrompts.length} / {prompts.length}</span>}>
        <div className="filters">
          <input placeholder="Search prompts..." value={filters.q} onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))} />
          <select value={filters.prompt_type} onChange={(event) => setFilters((current) => ({ ...current, prompt_type: event.target.value }))}>
            <option value="">All types</option>
            {promptTypes.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
          <select value={filters.active} onChange={(event) => setFilters((current) => ({ ...current, active: event.target.value }))}>
            <option value="">Any version state</option>
            <option value="active">Latest active</option>
            <option value="inactive">No active latest</option>
          </select>
        </div>
        {promptsQuery.isLoading ? (
          <SkeletonBlock height={340} />
        ) : filteredPrompts.length === 0 ? (
          <StateScreen title="Sin prompts" body="Crea un prompt para empezar a reducir friccion con ChatGPT Web." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Title</th><th>Type</th><th>Tags</th><th>Latest</th><th>Updated</th></tr></thead>
              <tbody>
                {filteredPrompts.map((prompt) => {
                  const tags = Array.isArray(prompt.metadata?.tags) ? prompt.metadata.tags.join(", ") : "—";
                  return (
                    <tr key={prompt.id}>
                      <td><Link to={`/radar/prompts/${prompt.id}`}>{prompt.title}</Link></td>
                      <td>{prompt.prompt_type}</td>
                      <td>{tags}</td>
                      <td>{prompt.latest_version ? `v${prompt.latest_version}${prompt.latest_version_is_active ? " active" : ""}` : "—"}</td>
                      <td>{formatDateTime(prompt.updated_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </RadarShell>
  );
}

function RadarPromptDetailPageLegacy() {
  const { promptId = "" } = useParams();
  const queryClient = useQueryClient();
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [versionForm, setVersionForm] = useState({ body: "", output_schema: "{\n  \"_radar_export\": true\n}", filename_pattern: "radar_candidate_*.json", changelog: "", is_active: true });

  const promptQuery = useQuery({ queryKey: ["radar-prompt", promptId], queryFn: () => getRadarPrompt(promptId), enabled: Boolean(promptId) });
  const versionsQuery = useQuery({ queryKey: ["radar-prompt-versions", promptId], queryFn: () => getRadarPromptVersions(promptId), enabled: Boolean(promptId) });
  const createVersionMutation = useMutation({
    mutationFn: () =>
      createRadarPromptVersion(promptId, {
        body: versionForm.body,
        output_schema: jsonFromTextarea(versionForm.output_schema),
        filename_pattern: nullIfBlank(versionForm.filename_pattern),
        changelog: nullIfBlank(versionForm.changelog),
        is_active: versionForm.is_active,
      }),
    onSuccess: (version) => {
      setSelectedVersionId(version.id);
      setVersionForm({ body: "", output_schema: "{\n  \"_radar_export\": true\n}", filename_pattern: "radar_candidate_*.json", changelog: "", is_active: true });
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-versions", promptId] });
      queryClient.invalidateQueries({ queryKey: ["radar-prompts"] });
    },
  });

  const prompt = promptQuery.data;
  const versions = versionsQuery.data || [];
  const selectedVersion = versions.find((item) => item.id === selectedVersionId) || versions.find((item) => item.is_active) || versions[0];

  useEffect(() => {
    if (!selectedVersionId && selectedVersion) {
      setSelectedVersionId(selectedVersion.id);
    }
  }, [selectedVersion, selectedVersionId]);

  async function copySelected(includeSchema: boolean) {
    if (!selectedVersion) {
      return;
    }
    const content = includeSchema
      ? `${selectedVersion.body}\n\nExpected JSON schema:\n${prettyJson(selectedVersion.output_schema)}`
      : selectedVersion.body;
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(content);
      setCopyStatus(includeSchema ? "Prompt + schema copied." : "Prompt copied.");
    } catch {
      setCopyStatus(null);
      setCopyError("No pude copiar al clipboard. Selecciona el texto del prompt manualmente o enfoca la ventana y reintenta.");
    }
  }

  return (
    <RadarShell title={prompt?.title || "Radar Prompt"} subtitle="Prompt versionado para ejecucion externa: copiar, abrir web, descargar JSON y volver a importar.">
      {promptQuery.isLoading ? (
        <SkeletonBlock height={420} />
      ) : promptQuery.isError || !prompt ? (
        <StateScreen title="Prompt no encontrado" body={promptQuery.error?.message || "No pude cargar este prompt."} tone="bad" />
      ) : (
        <div className="dashboard-grid">
          <Section title="Prompt metadata" eyebrow={prompt.key} stagger={0}>
            <article className="list-card">
              <div className="row spread"><h4>{prompt.title}</h4><span className="meta-pill">{prompt.prompt_type}</span></div>
              <p>{prompt.description || "Sin descripcion."}</p>
              <KeyValueList
                items={[
                  { label: "latest_version", value: prompt.latest_version ? `v${prompt.latest_version}` : "—" },
                  { label: "updated_at", value: formatDateTime(prompt.updated_at) },
                  { label: "suggested_filename", value: selectedVersion?.filename_pattern || "radar_*.json" },
                ]}
              />
            </article>
            <div className="radar-flow-steps">
              <span>1. Copy Prompt</span>
              <span>2. Open ChatGPT Web</span>
              <span>3. Download radar_*.json</span>
              <span>4. Go to Import JSON</span>
            </div>
          </Section>

          <Section title="Versions" eyebrow="Copy workflow" stagger={1}>
            {versionsQuery.isLoading ? (
              <SkeletonBlock height={220} />
            ) : versions.length === 0 ? (
              <StateScreen title="Sin versiones" body="Crea la primera version para poder copiar el prompt." />
            ) : (
              <>
                <select value={selectedVersion?.id || ""} onChange={(event) => setSelectedVersionId(event.target.value)}>
                  {versions.map((version) => <option key={version.id} value={version.id}>v{version.version}{version.is_active ? " active" : ""}</option>)}
                </select>
                {selectedVersion ? (
                  <article className="list-card">
                    <pre className="json-block prompt-body-block">{selectedVersion.body}</pre>
                    <div className="hero-actions">
                      <button className="primary-button" type="button" onClick={() => copySelected(false)}>Copy Prompt</button>
                      <button className="secondary-button" type="button" onClick={() => copySelected(true)}>Copy Prompt + JSON Schema</button>
                      <button className="secondary-button" type="button" onClick={() => window.open("https://chatgpt.com", "_blank")}>Open ChatGPT Web</button>
                      <button className="secondary-button" type="button" onClick={() => window.open("https://claude.ai", "_blank")}>Open Claude Web</button>
                      <Link className="secondary-button" to="/radar/import">Go to Import JSON</Link>
                    </div>
                    {copyStatus ? <p className="form-success">{copyStatus}</p> : null}
                    {copyError ? <p className="form-error">{copyError}</p> : null}
                    <span className="eyebrow">output_schema</span>
                    <pre className="json-block">{prettyJson(selectedVersion.output_schema)}</pre>
                  </article>
                ) : null}
              </>
            )}
          </Section>

          <Section title="New version" eyebrow="No API execution" stagger={2}>
            <form
              className="radar-form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                createVersionMutation.mutate();
              }}
            >
              <label className="wide-field">Body<textarea value={versionForm.body} onChange={(event) => setVersionForm((current) => ({ ...current, body: event.target.value }))} required /></label>
              <label className="wide-field">Output schema<textarea value={versionForm.output_schema} onChange={(event) => setVersionForm((current) => ({ ...current, output_schema: event.target.value }))} /></label>
              <label>Suggested filename<input value={versionForm.filename_pattern} onChange={(event) => setVersionForm((current) => ({ ...current, filename_pattern: event.target.value }))} /></label>
              <label>Changelog<input value={versionForm.changelog} onChange={(event) => setVersionForm((current) => ({ ...current, changelog: event.target.value }))} /></label>
              <label className="checkbox-row"><input type="checkbox" checked={versionForm.is_active} onChange={(event) => setVersionForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
              <div className="hero-actions wide-field">
                <button className="primary-button" type="submit" disabled={createVersionMutation.isPending}>{createVersionMutation.isPending ? "Creating..." : "Create version"}</button>
                {createVersionMutation.error instanceof Error ? <span className="form-error">{createVersionMutation.error.message}</span> : null}
              </div>
            </form>
          </Section>
        </div>
      )}
    </RadarShell>
  );
}

function RadarPromptDetailPage() {
  const { promptId = "" } = useParams();
  const queryClient = useQueryClient();
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [renderResult, setRenderResult] = useState<RadarPromptRenderResult | null>(null);
  const [renderForm, setRenderForm] = useState({ candidate_id: "", target_tool: "chatgpt_web", model_label: "", notes: "" });
  const [renderVariables, setRenderVariables] = useState<Record<string, string>>({});
  const [versionForm, setVersionForm] = useState({
    body: "",
    output_schema: "{\n  \"meta\": {\n    \"promptRunId\": \"string\"\n  }\n}",
    variables_schema: "{\n  \"properties\": {}\n}",
    filename_pattern: "radar_candidate_*.json",
    changelog: "",
    system_notes: "",
    is_active: true,
  });

  const promptQuery = useQuery({ queryKey: ["radar-prompt", promptId], queryFn: () => getRadarPrompt(promptId), enabled: Boolean(promptId) });
  const versionsQuery = useQuery({ queryKey: ["radar-prompt-versions", promptId], queryFn: () => getRadarPromptVersions(promptId), enabled: Boolean(promptId) });
  const candidatesQuery = useQuery({ queryKey: ["radar-candidates"], queryFn: getRadarCandidates });
  const promptRunsQuery = useQuery({
    queryKey: ["radar-prompt-runs", promptId],
    queryFn: () => getRadarPromptRuns({ prompt_id: promptId, limit: "6" }),
    enabled: Boolean(promptId),
  });

  const createVersionMutation = useMutation({
    mutationFn: () =>
      createRadarPromptVersion(promptId, {
        body: versionForm.body,
        output_schema: jsonFromTextarea(versionForm.output_schema),
        variables_schema: jsonFromTextarea(versionForm.variables_schema),
        filename_pattern: nullIfBlank(versionForm.filename_pattern),
        changelog: nullIfBlank(versionForm.changelog),
        system_notes: nullIfBlank(versionForm.system_notes),
        is_active: versionForm.is_active,
      }),
    onSuccess: (version) => {
      setSelectedVersionId(version.id);
      setVersionForm({
        body: "",
        output_schema: "{\n  \"meta\": {\n    \"promptRunId\": \"string\"\n  }\n}",
        variables_schema: "{\n  \"properties\": {}\n}",
        filename_pattern: "radar_candidate_*.json",
        changelog: "",
        system_notes: "",
        is_active: true,
      });
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-versions", promptId] });
      queryClient.invalidateQueries({ queryKey: ["radar-prompts"] });
    },
  });

  const renderMutation = useMutation({
    mutationFn: () =>
      renderRadarPromptVersion(promptId, selectedVersion?.id || selectedVersionId, {
        candidate_id: nullIfBlank(renderForm.candidate_id),
        target_tool: renderForm.target_tool as "chatgpt_web" | "claude_web" | "codex" | "other",
        model_label: nullIfBlank(renderForm.model_label),
        variables: renderVariables,
        notes: nullIfBlank(renderForm.notes),
      }),
    onSuccess: (result) => {
      setRenderResult(result);
      setCopyStatus(null);
      setCopyError(null);
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-runs"] });
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-runs", promptId] });
    },
  });

  const markCopiedMutation = useMutation({
    mutationFn: markRadarPromptRunCopied,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-runs"] });
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-runs", promptId] });
    },
  });

  const prompt = promptQuery.data;
  const versions = versionsQuery.data || [];
  const candidates = candidatesQuery.data || [];
  const promptRuns = promptRunsQuery.data || [];
  const selectedVersion = versions.find((item) => item.id === selectedVersionId) || versions.find((item) => item.is_active) || versions[0];
  const variableNames = radarVariableNames(selectedVersion?.variables_schema);

  useEffect(() => {
    if (!selectedVersionId && selectedVersion) {
      setSelectedVersionId(selectedVersion.id);
    }
  }, [selectedVersion, selectedVersionId]);

  useEffect(() => {
    setRenderVariables((current) => {
      const next: Record<string, string> = {};
      variableNames.forEach((name) => {
        next[name] = current[name] || "";
      });
      return next;
    });
  }, [selectedVersionId, variableNames.join("|")]);

  async function copyRenderedPrompt() {
    if (!renderResult) {
      return;
    }
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(renderResult.rendered_prompt);
      setCopyStatus("Rendered prompt copied. Prompt run is waiting for import.");
      markCopiedMutation.mutate(renderResult.prompt_run_id);
    } catch {
      setCopyStatus(null);
      setCopyError("No pude copiar al clipboard. El prompt queda visible para seleccionar manualmente.");
    }
  }

  return (
    <RadarShell title={prompt?.title || "Radar Prompt"} subtitle="Render de prompts versionados para ejecucion externa, sin API ni automatizacion web.">
      {promptQuery.isLoading ? (
        <SkeletonBlock height={420} />
      ) : promptQuery.isError || !prompt ? (
        <StateScreen title="Prompt no encontrado" body={promptQuery.error?.message || "No pude cargar este prompt."} tone="bad" />
      ) : (
        <div className="dashboard-grid">
          <Section title="Prompt metadata" eyebrow={prompt.key} stagger={0}>
            <article className="list-card">
              <div className="row spread"><h4>{prompt.title}</h4><span className="meta-pill">{prompt.prompt_type}</span></div>
              <p>{prompt.description || "Sin descripcion."}</p>
              <KeyValueList
                items={[
                  { label: "latest_version", value: prompt.latest_version ? `v${prompt.latest_version}` : "—" },
                  { label: "updated_at", value: formatDateTime(prompt.updated_at) },
                  { label: "suggested_filename", value: selectedVersion?.filename_pattern || "radar_*.json" },
                ]}
              />
            </article>
            <div className="radar-flow-steps">
              <span>1. Render with candidate + variables</span>
              <span>2. Copy rendered prompt</span>
              <span>3. Run in ChatGPT Web / Claude Web</span>
              <span>4. Import JSON with meta.promptRunId</span>
            </div>
          </Section>

          <Section title="Run externally" eyebrow="Prompt run" stagger={1}>
            {versions.length === 0 ? (
              <StateScreen title="Sin versiones" body="Crea una version antes de renderizar." />
            ) : (
              <form
                className="radar-form-grid"
                onSubmit={(event) => {
                  event.preventDefault();
                  renderMutation.mutate();
                }}
              >
                <label>
                  Version
                  <select value={selectedVersion?.id || ""} onChange={(event) => setSelectedVersionId(event.target.value)}>
                    {versions.map((version) => <option key={version.id} value={version.id}>v{version.version}{version.is_active ? " active" : ""}</option>)}
                  </select>
                </label>
                <label>
                  Candidate
                  <select value={renderForm.candidate_id} onChange={(event) => setRenderForm((current) => ({ ...current, candidate_id: event.target.value }))}>
                    <option value="">Sin candidate</option>
                    {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name}</option>)}
                  </select>
                </label>
                <label>
                  Target tool
                  <select value={renderForm.target_tool} onChange={(event) => setRenderForm((current) => ({ ...current, target_tool: event.target.value }))}>
                    <option value="chatgpt_web">ChatGPT Web</option>
                    <option value="claude_web">Claude Web</option>
                    <option value="codex">Codex</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label>Model label<input value={renderForm.model_label} onChange={(event) => setRenderForm((current) => ({ ...current, model_label: event.target.value }))} placeholder="GPT-5.5 Thinking" /></label>
                {variableNames.map((name) => (
                  <label key={name}>
                    variables.{name}
                    <input value={renderVariables[name] || ""} onChange={(event) => setRenderVariables((current) => ({ ...current, [name]: event.target.value }))} />
                  </label>
                ))}
                <label className="wide-field">Notes<textarea value={renderForm.notes} onChange={(event) => setRenderForm((current) => ({ ...current, notes: event.target.value }))} /></label>
                <div className="hero-actions wide-field">
                  <button className="primary-button" type="submit" disabled={renderMutation.isPending || !selectedVersion}>
                    {renderMutation.isPending ? "Rendering..." : "Render Prompt"}
                  </button>
                  {renderMutation.error instanceof Error ? <span className="form-error">{renderMutation.error.message}</span> : null}
                </div>
              </form>
            )}
            {renderResult ? (
              <article className="list-card">
                <KeyValueList
                  items={[
                    { label: "prompt_run_id", value: renderResult.prompt_run_id },
                    { label: "expected_filename", value: renderResult.expected_filename },
                    { label: "target_tool", value: renderResult.target_tool },
                  ]}
                />
                {renderResult.warnings.length ? renderResult.warnings.map((warning) => <p className="form-error" key={warning}>{warning}</p>) : null}
                <textarea className="rendered-prompt-preview" readOnly value={renderResult.rendered_prompt} />
                <div className="hero-actions">
                  <button className="primary-button" type="button" onClick={copyRenderedPrompt}>Copy Prompt</button>
                  <button className="secondary-button" type="button" onClick={() => window.open("https://chatgpt.com", "_blank")}>Open ChatGPT Web</button>
                  <button className="secondary-button" type="button" onClick={() => window.open("https://claude.ai", "_blank")}>Open Claude Web</button>
                  <Link className="secondary-button" to={`/radar/import?candidate_id=${renderForm.candidate_id}&prompt_run_id=${renderResult.prompt_run_id}`}>Go to Import JSON</Link>
                </div>
                {copyStatus ? <p className="form-success">{copyStatus}</p> : null}
                {copyError ? <p className="form-error">{copyError}</p> : null}
              </article>
            ) : null}
          </Section>

          <Section title="Versions" eyebrow="Template source" stagger={2}>
            {versionsQuery.isLoading ? (
              <SkeletonBlock height={220} />
            ) : versions.length === 0 ? (
              <StateScreen title="Sin versiones" body="Crea la primera version para poder renderizar." />
            ) : selectedVersion ? (
              <article className="list-card">
                <pre className="json-block prompt-body-block">{selectedVersion.body}</pre>
                <span className="eyebrow">variables_schema</span>
                <pre className="json-block">{prettyJson(selectedVersion.variables_schema)}</pre>
                <span className="eyebrow">output_schema</span>
                <pre className="json-block">{prettyJson(selectedVersion.output_schema)}</pre>
              </article>
            ) : null}
          </Section>

          <Section title="Recent prompt runs" eyebrow="This prompt" stagger={3}>
            {promptRunsQuery.isLoading ? (
              <SkeletonBlock height={200} />
            ) : promptRuns.length === 0 ? (
              <StateScreen title="Sin prompt runs" body="Los renders externos van a aparecer aca." />
            ) : (
              <div className="stack-list compact">
                {promptRuns.map((run) => (
                  <article className="list-card" key={run.id}>
                    <div className="row spread"><h4>{run.expected_filename || run.id}</h4><StatusChip value={run.status} /></div>
                    <p>{run.model_label || run.target_tool}</p>
                    <div className="meta-row"><span>{formatDateTime(run.created_at)}</span><Link to="/radar/prompt-runs">View runs</Link></div>
                  </article>
                ))}
              </div>
            )}
          </Section>

          <Section title="New version" eyebrow="Template + schema" stagger={4}>
            <form
              className="radar-form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                createVersionMutation.mutate();
              }}
            >
              <label className="wide-field">Body<textarea value={versionForm.body} onChange={(event) => setVersionForm((current) => ({ ...current, body: event.target.value }))} required placeholder="Use {{candidate.name}} and {{variables.angle}} placeholders." /></label>
              <label className="wide-field">Variables schema<textarea value={versionForm.variables_schema} onChange={(event) => setVersionForm((current) => ({ ...current, variables_schema: event.target.value }))} /></label>
              <label className="wide-field">Output schema<textarea value={versionForm.output_schema} onChange={(event) => setVersionForm((current) => ({ ...current, output_schema: event.target.value }))} /></label>
              <label>Suggested filename<input value={versionForm.filename_pattern} onChange={(event) => setVersionForm((current) => ({ ...current, filename_pattern: event.target.value }))} /></label>
              <label>Changelog<input value={versionForm.changelog} onChange={(event) => setVersionForm((current) => ({ ...current, changelog: event.target.value }))} /></label>
              <label className="wide-field">System notes<textarea value={versionForm.system_notes} onChange={(event) => setVersionForm((current) => ({ ...current, system_notes: event.target.value }))} /></label>
              <label className="checkbox-row"><input type="checkbox" checked={versionForm.is_active} onChange={(event) => setVersionForm((current) => ({ ...current, is_active: event.target.checked }))} /> active</label>
              <div className="hero-actions wide-field">
                <button className="primary-button" type="submit" disabled={createVersionMutation.isPending}>{createVersionMutation.isPending ? "Creating..." : "Create version"}</button>
                {createVersionMutation.error instanceof Error ? <span className="form-error">{createVersionMutation.error.message}</span> : null}
              </div>
            </form>
          </Section>
        </div>
      )}
    </RadarShell>
  );
}

function RadarPromptRunsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({ candidate_id: "", prompt_id: "", status: "", q: "" });
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const candidatesQuery = useQuery({ queryKey: ["radar-candidates"], queryFn: getRadarCandidates });
  const promptsQuery = useQuery({ queryKey: ["radar-prompts"], queryFn: getRadarPrompts });
  const runsQuery = useQuery({
    queryKey: ["radar-prompt-runs", filters.candidate_id, filters.prompt_id, filters.status],
    queryFn: () => getRadarPromptRuns({ candidate_id: filters.candidate_id, prompt_id: filters.prompt_id, status: filters.status, limit: "50" }),
  });
  const cancelMutation = useMutation({
    mutationFn: cancelRadarPromptRun,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["radar-prompt-runs"] }),
  });

  const candidates = candidatesQuery.data || [];
  const prompts = promptsQuery.data || [];
  const promptById = new Map(prompts.map((prompt) => [prompt.id, prompt]));
  const candidateById = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  const q = filters.q.trim().toLowerCase();
  const runs = (runsQuery.data || []).filter((run) => {
    const prompt = promptById.get(run.prompt_id);
    const candidate = run.candidate_id ? candidateById.get(run.candidate_id) : null;
    const haystack = [run.id, run.expected_filename, run.model_label, run.target_tool, run.status, prompt?.title, candidate?.name].filter(Boolean).join(" ").toLowerCase();
    return !q || haystack.includes(q);
  });
  const selectedRun = runs.find((run) => run.id === selectedRunId) || runs[0] || null;

  async function copyRunAgain(run: RadarPromptRun) {
    try {
      await navigator.clipboard.writeText(run.rendered_prompt);
    } catch {
      // The rendered prompt remains visible as a selectable fallback.
    }
  }

  return (
    <RadarShell title="Radar Prompt Runs" subtitle="Ejecuciones externas/manuales de prompts, sin API ni browser automation.">
      <div className="detail-layout">
        <Section title="Prompt runs" eyebrow="Filters" stagger={0} aside={<span className="meta-pill">{runs.length}</span>}>
          <div className="filters">
            <input placeholder="Search runs..." value={filters.q} onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))} />
            <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
              <option value="">Any status</option>
              <option value="created">created</option>
              <option value="waiting_import">waiting_import</option>
              <option value="applied">applied</option>
              <option value="cancelled">cancelled</option>
              <option value="failed">failed</option>
            </select>
            <select value={filters.prompt_id} onChange={(event) => setFilters((current) => ({ ...current, prompt_id: event.target.value }))}>
              <option value="">Any prompt</option>
              {prompts.map((prompt) => <option key={prompt.id} value={prompt.id}>{prompt.title}</option>)}
            </select>
            <select value={filters.candidate_id} onChange={(event) => setFilters((current) => ({ ...current, candidate_id: event.target.value }))}>
              <option value="">Any candidate</option>
              {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name}</option>)}
            </select>
          </div>
          {runsQuery.isLoading ? (
            <SkeletonBlock height={360} />
          ) : runs.length === 0 ? (
            <StateScreen title="Sin prompt runs" body="Renderiza un prompt desde Prompt Detail para crear el primer run externo." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Prompt</th><th>Candidate</th><th>Tool</th><th>Status</th><th>Expected filename</th><th>Created</th><th>Apply log</th></tr></thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} onClick={() => setSelectedRunId(run.id)}>
                      <td>{promptById.get(run.prompt_id)?.title || run.prompt_id}</td>
                      <td>{run.candidate_id ? candidateById.get(run.candidate_id)?.name || run.candidate_id : "—"}</td>
                      <td>{run.model_label || run.target_tool}</td>
                      <td><StatusChip value={run.status} /></td>
                      <td>{run.expected_filename || "—"}</td>
                      <td>{formatDateTime(run.created_at)}</td>
                      <td>{run.apply_log_id ? <Link to="/radar/apply-logs">linked</Link> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="Run detail" eyebrow="Rendered prompt" stagger={1}>
          {selectedRun ? (
            <article className="list-card">
              <div className="row spread"><h4>{selectedRun.expected_filename || selectedRun.id}</h4><StatusChip value={selectedRun.status} /></div>
              <KeyValueList
                items={[
                  { label: "prompt_run_id", value: selectedRun.id },
                  { label: "prompt", value: promptById.get(selectedRun.prompt_id)?.title || selectedRun.prompt_id },
                  { label: "candidate", value: selectedRun.candidate_id ? candidateById.get(selectedRun.candidate_id)?.name || selectedRun.candidate_id : "—" },
                  { label: "tool", value: selectedRun.model_label || selectedRun.target_tool },
                  { label: "apply_log", value: selectedRun.apply_log_id || "—" },
                ]}
              />
              <textarea className="rendered-prompt-preview" readOnly value={selectedRun.rendered_prompt} />
              <div className="hero-actions">
                <button className="secondary-button" type="button" onClick={() => copyRunAgain(selectedRun)}>Copy again</button>
                <Link className="secondary-button" to={`/radar/import?candidate_id=${selectedRun.candidate_id || ""}&prompt_run_id=${selectedRun.id}`}>Go to Import JSON</Link>
                {selectedRun.status !== "applied" && selectedRun.status !== "cancelled" ? (
                  <button className="danger-button" type="button" onClick={() => cancelMutation.mutate(selectedRun.id)}>Cancel</button>
                ) : null}
              </div>
            </article>
          ) : (
            <StateScreen title="Selecciona un prompt run" body="Elegi una fila para ver y copiar el prompt renderizado." />
          )}
        </Section>
      </div>
    </RadarShell>
  );
}

function RadarApplyLogsPage() {
  const [filters, setFilters] = useState({ status: "", candidate_id: "", model_used: "" });
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const candidatesQuery = useQuery({ queryKey: ["radar-candidates"], queryFn: getRadarCandidates });
  const logsQuery = useQuery({
    queryKey: ["radar-apply-logs", filters.status, filters.candidate_id],
    queryFn: () => getRadarApplyLogs({ status: filters.status, candidate_id: filters.candidate_id, limit: "50" }),
  });

  const candidates = candidatesQuery.data || [];
  const logs = (logsQuery.data || []).filter((item) => !filters.model_used || (item.model_used || "").toLowerCase().includes(filters.model_used.toLowerCase()));
  const candidateById = new Map(candidates.map((item) => [item.id, item]));
  const selectedLog = logs.find((item) => item.id === selectedLogId) || logs[0] || null;

  return (
    <RadarShell title="Radar Apply Logs" subtitle="Historial read-only de dry-runs y applies manuales para auditar imports JSON.">
      <div className="detail-layout">
        <Section title="Logs" eyebrow="Filters" stagger={0} aside={<span className="meta-pill">{logs.length}</span>}>
          <div className="filters">
            <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
              <option value="">Any status</option>
              <option value="applied">applied</option>
              <option value="dry_run">dry_run</option>
              <option value="failed">failed</option>
            </select>
            <select value={filters.candidate_id} onChange={(event) => setFilters((current) => ({ ...current, candidate_id: event.target.value }))}>
              <option value="">Any candidate</option>
              {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name}</option>)}
            </select>
            <input placeholder="model_used" value={filters.model_used} onChange={(event) => setFilters((current) => ({ ...current, model_used: event.target.value }))} />
          </div>
          {logsQuery.isLoading ? (
            <SkeletonBlock height={360} />
          ) : logs.length === 0 ? (
            <StateScreen title="Sin logs" body="No hay apply logs para estos filtros." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Status</th><th>Candidate</th><th>Model</th><th>Source</th><th>Created</th><th>Error</th></tr></thead>
                <tbody>
                  {logs.map((item) => (
                    <tr key={item.id} onClick={() => setSelectedLogId(item.id)}>
                      <td><StatusChip value={item.status} /></td>
                      <td>{item.candidate_id ? candidateById.get(item.candidate_id)?.name || item.candidate_id : "—"}</td>
                      <td>{item.model_used || "—"}</td>
                      <td>{item.source_type}</td>
                      <td>{formatDateTime(item.created_at)}</td>
                      <td>{item.error_message || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="Log detail" eyebrow="JSON payload" stagger={1}>
          {selectedLog ? (
            <article className="list-card">
              <div className="row spread"><h4>{selectedLog.id}</h4><StatusChip value={selectedLog.status} /></div>
              <KeyValueList
                items={[
                  { label: "candidate", value: selectedLog.candidate_id || "—" },
                  { label: "prompt", value: selectedLog.prompt_id || "—" },
                  { label: "prompt_version", value: selectedLog.prompt_version_id || "—" },
                  { label: "model", value: selectedLog.model_used || "—" },
                  { label: "source", value: selectedLog.source_type },
                  { label: "created_at", value: formatDateTime(selectedLog.created_at) },
                ]}
              />
              {selectedLog.error_message ? <p className="form-error">{selectedLog.error_message}</p> : null}
              <span className="eyebrow">json_payload</span>
              <pre className="json-block">{prettyJson(selectedLog.json_payload)}</pre>
              <span className="eyebrow">applied_changes</span>
              <pre className="json-block">{prettyJson(selectedLog.applied_changes)}</pre>
            </article>
          ) : (
            <StateScreen title="Selecciona un log" body="Elegi una fila para ver el JSON aplicado o fallido." />
          )}
        </Section>
      </div>
    </RadarShell>
  );
}

function RadarSettingsPage() {
  const configQuery = useQuery({ queryKey: ["radar-config"], queryFn: getRadarConfig });
  const config = configQuery.data || [];

  return (
    <RadarShell title="Radar Settings" subtitle="Taxonomias actuales de Radar. En Fase 3 quedan read-only para evitar reglas prematuras.">
      <Section title="Taxonomies" eyebrow="Read-only config" stagger={0}>
        {configQuery.isLoading ? (
          <SkeletonBlock height={420} />
        ) : config.length === 0 ? (
          <StateScreen title="Sin config" body="No encontre valores en radar_config." tone="bad" />
        ) : (
          <div className="settings-grid">
            {radarTaxonomyKeys.map((key, index) => {
              const item = config.find((entry) => entry.key === key);
              return (
                <article className="list-card reveal" key={key} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread"><h4>{radarCandidateFieldLabels[key]}</h4><span className="meta-pill">{radarConfigValues(config, key).length}</span></div>
                  <p>{item?.description || `Radar taxonomy for ${key}`}</p>
                  <div className="tag-list">
                    {radarConfigValues(config, key).map((value) => <span className="meta-pill" key={value}>{value}</span>)}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Section>
    </RadarShell>
  );
}

function RadarImportPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedCandidateId = searchParams.get("candidate_id") ?? "";
  const selectedPromptRunId = searchParams.get("prompt_run_id") ?? "";
  const [jsonInput, setJsonInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [lastSourceType, setLastSourceType] = useState<"manual_paste" | "drag_drop">("manual_paste");
  const [lastResult, setLastResult] = useState<RadarApplyResult | null>(null);
  const [lastPreview, setLastPreview] = useState<RadarApplyResult | null>(null);

  const candidatesQuery = useQuery({
    queryKey: ["radar-candidates"],
    queryFn: getRadarCandidates,
  });
  const recentLogsQuery = useQuery({
    queryKey: ["radar-apply-logs", "recent"],
    queryFn: () => getRadarApplyLogs({ limit: "12" }),
  });
  const waitingPromptRunsQuery = useQuery({
    queryKey: ["radar-prompt-runs", "waiting-import"],
    queryFn: () => getRadarPromptRuns({ status: "waiting_import", limit: "8" }),
  });
  const fileImportsQuery = useQuery({
    queryKey: ["radar-file-imports", "recent"],
    queryFn: () => getRadarFileImports({ limit: "10" }),
  });
  const selectedCandidateQuery = useQuery({
    queryKey: ["radar-candidate", selectedCandidateId],
    queryFn: () => getRadarCandidate(selectedCandidateId),
    enabled: Boolean(selectedCandidateId),
  });
  const selectedEvidenceQuery = useQuery({
    queryKey: ["radar-evidence", selectedCandidateId],
    queryFn: () => getRadarCandidateEvidence(selectedCandidateId),
    enabled: Boolean(selectedCandidateId),
  });
  const selectedLogsQuery = useQuery({
    queryKey: ["radar-apply-logs", selectedCandidateId],
    queryFn: () => getRadarApplyLogs({ candidate_id: selectedCandidateId, limit: "8" }),
    enabled: Boolean(selectedCandidateId),
  });

  const previewMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => applyRadarJson(payload, { dryRun: true }),
    onSuccess: (result) => {
      setLastPreview(result);
      setLastResult(null);
      const candidateId = result.candidate_id;
      if (candidateId) {
        setSearchParams((current) => {
          const next = new URLSearchParams(current);
          next.set("candidate_id", candidateId);
          return next;
        });
      }
      queryClient.invalidateQueries({ queryKey: ["radar-apply-logs"] });
    },
  });

  const applyMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => applyRadarJson(payload),
    onSuccess: (result) => {
      setLastResult(result);
      setLastPreview(null);
      const candidateId = result.candidate_id;
      if (candidateId) {
        setSearchParams((current) => {
          const next = new URLSearchParams(current);
          next.set("candidate_id", candidateId);
          return next;
        });
      }
      queryClient.invalidateQueries({ queryKey: ["radar-candidates"] });
      queryClient.invalidateQueries({ queryKey: ["radar-candidate"] });
      queryClient.invalidateQueries({ queryKey: ["radar-evidence"] });
      queryClient.invalidateQueries({ queryKey: ["radar-apply-logs"] });
      queryClient.invalidateQueries({ queryKey: ["radar-prompt-runs"] });
      queryClient.invalidateQueries({ queryKey: ["radar-file-imports"] });
    },
  });

  const candidates = (candidatesQuery.data as RadarCandidate[] | undefined) || [];
  const selectedCandidate = selectedCandidateQuery.data as RadarCandidate | undefined;
  const evidence = (selectedEvidenceQuery.data as RadarEvidence[] | undefined) || [];
  const candidateLogs = (selectedLogsQuery.data as RadarApplyLog[] | undefined) || [];
  const recentLogs = (recentLogsQuery.data as RadarApplyLog[] | undefined) || [];
  const waitingPromptRuns = (waitingPromptRunsQuery.data as RadarPromptRun[] | undefined) || [];
  const fileImports = (fileImportsQuery.data as RadarFileImport[] | undefined) || [];

  function injectSourceType(payload: Record<string, unknown>) {
    const cloned = JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
    if (cloned._radar_export === true && cloned.data && typeof cloned.data === "object" && !Array.isArray(cloned.data)) {
      const wrapperData = cloned.data as Record<string, unknown>;
      const meta =
        wrapperData.meta && typeof wrapperData.meta === "object" && !Array.isArray(wrapperData.meta)
          ? { ...(wrapperData.meta as Record<string, unknown>) }
          : {};
      meta.sourceType = lastSourceType;
      wrapperData.meta = meta;
      cloned.data = wrapperData;
      return cloned;
    }

    const meta =
      cloned.meta && typeof cloned.meta === "object" && !Array.isArray(cloned.meta)
        ? { ...(cloned.meta as Record<string, unknown>) }
        : {};
    meta.sourceType = lastSourceType;
    cloned.meta = meta;
    return cloned;
  }

  function parseCurrentInput() {
    if (!jsonInput.trim()) {
      throw new Error("Pegá o arrastrá un JSON antes de validar.");
    }
    try {
      const parsed = JSON.parse(jsonInput) as Record<string, unknown>;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Radar import espera un JSON object en el nivel raíz.");
      }
      return injectSourceType(parsed);
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error("No pude parsear el JSON.");
    }
  }

  function runPreview() {
    setInputError(null);
    try {
      previewMutation.mutate(parseCurrentInput());
    } catch (error) {
      setLastPreview(null);
      setLastResult(null);
      setInputError(error instanceof Error ? error.message : "No pude validar el JSON.");
    }
  }

  function runApply() {
    setInputError(null);
    try {
      applyMutation.mutate(parseCurrentInput());
    } catch (error) {
      setLastResult(null);
      setInputError(error instanceof Error ? error.message : "No pude aplicar el JSON.");
    }
  }

  function handleFileDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (!file) {
      return;
    }
    if (!file.name.toLowerCase().endsWith(".json")) {
      setInputError("Solo se aceptan archivos .json en esta fase.");
      return;
    }
    file
      .text()
      .then((content) => {
        setJsonInput(content);
        setLastSourceType("drag_drop");
        setInputError(null);
      })
      .catch(() => {
        setInputError("No pude leer el archivo arrastrado.");
      });
  }

  const activeResult = lastResult || lastPreview;
  const mutationError =
    (applyMutation.error instanceof Error ? applyMutation.error.message : null) ||
    (previewMutation.error instanceof Error ? previewMutation.error.message : null);

  return (
    <RadarShell
      title="Radar Import"
      subtitle="Loop manual mínimo para pegar o arrastrar JSON Radar, validar en dry-run y aplicar sobre un candidate existente."
    >
      <div className="dashboard-grid">
        <Section title="Apply JSON" eyebrow="Manual import" stagger={0}>
          {inputError ? <p className="form-error">{inputError}</p> : null}
          {mutationError ? <p className="form-error">{mutationError}</p> : null}
          {selectedPromptRunId ? <p className="panel-note">Prompt run seleccionado: {selectedPromptRunId}</p> : null}
          {lastResult?.ok ? <p className="form-success">Apply real persistido correctamente.</p> : null}
          {lastPreview?.ok ? <p className="form-success">Dry-run válido. Ya tenés preview de lo que se aplicaría.</p> : null}

          <div
            className="radar-dropzone"
            onDragOver={(event) => {
              event.preventDefault();
            }}
            onDrop={handleFileDrop}
          >
            <strong>Drag & drop .json</strong>
            <p>O pegá el JSON manualmente. Esta fase no observa carpetas ni Downloads todavía.</p>
          </div>

          <div className="filters">
            <textarea
              className="radar-json-input"
              value={jsonInput}
              onChange={(event) => {
                setJsonInput(event.target.value);
                setLastSourceType("manual_paste");
              }}
              placeholder='Pegá acá un JSON Radar con wrapper `_radar_export` o payload `meta` + `updates`.'
            />
          </div>

          <div className="hero-actions">
            <button className="secondary-button" onClick={runPreview} disabled={previewMutation.isPending || applyMutation.isPending}>
              {previewMutation.isPending ? "Validando..." : "Validar / Preview"}
            </button>
            <button className="primary-button" onClick={runApply} disabled={applyMutation.isPending || previewMutation.isPending}>
              {applyMutation.isPending ? "Aplicando..." : "Aplicar"}
            </button>
            <span className="meta-pill">source_type: {lastSourceType}</span>
          </div>

          <div className="detail-layout">
            <Section title="Resultado" eyebrow="Preview / apply" stagger={1}>
              {activeResult ? (
                <div className="stack-list compact">
                  <article className="list-card">
                    <div className="row spread">
                      <h4>{activeResult.dry_run ? "Dry-run" : "Apply real"}</h4>
                      <StatusChip value={activeResult.dry_run ? "ready" : "done"} />
                    </div>
                    <KeyValueList
                      items={[
                        { label: "mode", value: activeResult.mode },
                        { label: "candidate_id", value: activeResult.candidate_id || "—" },
                        { label: "updates", value: activeResult.updates_applied.join(", ") || "—" },
                        { label: "evidence", value: String(activeResult.evidence_created) },
                        { label: "apply_log", value: activeResult.apply_log_id },
                        { label: "prompt_run", value: activeResult.prompt_run_id || "—" },
                      ]}
                    />
                    {activeResult.warnings.length ? (
                      <div className="stack-list compact">
                        {activeResult.warnings.map((warning) => (
                          <p className="form-error" key={warning}>
                            {warning}
                          </p>
                        ))}
                      </div>
                    ) : (
                      <p className="panel-note">Sin warnings para este import.</p>
                    )}
                  </article>
                </div>
              ) : (
                <StateScreen title="Sin preview todavía" body="Validá o aplicá un JSON para ver el resultado resumido en esta misma pantalla." />
              )}
            </Section>

            <Section title="Recent apply logs" eyebrow="Radar history" stagger={2} aside={<span className="meta-pill">{recentLogs.length} logs</span>}>
              {recentLogsQuery.isLoading ? (
                <SkeletonBlock height={220} />
              ) : recentLogs.length === 0 ? (
                <StateScreen title="Sin apply logs" body="Todavía no hay imports manuales registrados para Radar." />
              ) : (
                <div className="stack-list compact">
                  {recentLogs.map((item) => (
                    <article
                      className="list-card clickable-card"
                      key={item.id}
                      onClick={() => {
                        if (!item.candidate_id) {
                          return;
                        }
                        setSearchParams((current) => {
                          const next = new URLSearchParams(current);
                          next.set("candidate_id", item.candidate_id as string);
                          return next;
                        });
                      }}
                    >
                      <div className="row spread">
                        <h4>{item.candidate_id || "Sin candidate"}</h4>
                        <StatusChip value={item.status} />
                      </div>
                      <p>{item.error_message || item.notes || item.recognized_format || "Import log sin detalle extra."}</p>
                      <div className="meta-row">
                        <span>{item.source_type}</span>
                        <span>{formatDateTime(item.created_at)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </Section>
          </div>
        </Section>

        <Section title="File Inbox" eyebrow="Watcher local" stagger={3} aside={<span className="meta-pill">{fileImports.length} imports</span>}>
          <div className="stack-list compact">
            <article className="list-card">
              <KeyValueList
                items={[
                  { label: "inbox", value: "data/radar/inbox" },
                  { label: "processed", value: "data/radar/processed" },
                  { label: "failed", value: "data/radar/failed" },
                  { label: "pattern", value: "radar_*.json" },
                ]}
              />
              <p className="panel-note">
                1. CopiÃ¡ o ejecutÃ¡ un prompt en ChatGPT Web / Claude Web. 2. DescargÃ¡ el resultado como radar_*.json.
                3. Movelo a data/radar/inbox. 4. El watcher lo procesa y lo mueve a processed o failed.
              </p>
            </article>
            {fileImportsQuery.isLoading ? (
              <SkeletonBlock height={180} />
            ) : fileImports.length === 0 ? (
              <StateScreen title="Sin file imports" body="TodavÃ­a no hay archivos procesados por el watcher local." />
            ) : (
              fileImports.map((item) => (
                <article className="list-card" key={item.id}>
                  <div className="row spread">
                    <h4>{item.filename}</h4>
                    <StatusChip value={item.status} />
                  </div>
                  <p>{item.error_message || item.stored_path || item.original_path || "Import registrado sin detalle extra."}</p>
                  <KeyValueList
                    items={[
                      { label: "apply_log", value: item.apply_log_id || "â€”" },
                      { label: "hash", value: item.file_hash.slice(0, 16) },
                      { label: "created", value: formatDateTime(item.created_at) },
                      { label: "processed", value: formatDateTime(item.processed_at) },
                    ]}
                  />
                </article>
              ))
            )}
          </div>
        </Section>

        <Section title="Waiting prompt runs" eyebrow="External runs" stagger={3} aside={<span className="meta-pill">{waitingPromptRuns.length}</span>}>
          {waitingPromptRunsQuery.isLoading ? (
            <SkeletonBlock height={180} />
          ) : waitingPromptRuns.length === 0 ? (
            <StateScreen title="Sin prompt runs esperando import" body="Cuando copies un prompt renderizado, queda marcado como waiting_import." />
          ) : (
            <div className="stack-list compact">
              {waitingPromptRuns.map((run) => (
                <article className="list-card" key={run.id}>
                  <div className="row spread">
                    <h4>{run.expected_filename || run.id}</h4>
                    <StatusChip value={run.status} />
                  </div>
                  <p>{run.model_label || run.target_tool}</p>
                  <div className="hero-actions">
                    <Link className="secondary-button" to={`/radar/import?candidate_id=${run.candidate_id || ""}&prompt_run_id=${run.id}`}>
                      Import JSON for this run
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section
          title="Candidate detail"
          eyebrow="Minimal read-only"
          stagger={3}
          aside={
            <select
              value={selectedCandidateId}
              onChange={(event) => {
                const nextValue = event.target.value;
                setSearchParams((current) => {
                  const next = new URLSearchParams(current);
                  if (nextValue) {
                    next.set("candidate_id", nextValue);
                  } else {
                    next.delete("candidate_id");
                  }
                  return next;
                });
              }}
            >
              <option value="">Elegí una candidate</option>
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
            </select>
          }
        >
          {candidatesQuery.isLoading ? (
            <SkeletonBlock height={180} />
          ) : !selectedCandidateId ? (
            <StateScreen title="Seleccioná una candidate" body="Podés elegir una candidate desde el dropdown o dejar que el import seleccione automáticamente la afectada." />
          ) : selectedCandidateQuery.isLoading ? (
            <SkeletonBlock height={420} />
          ) : selectedCandidateQuery.isError ? (
            <StateScreen title="No pude cargar la candidate" body={selectedCandidateQuery.error.message} tone="bad" />
          ) : selectedCandidate ? (
            <div className="detail-layout">
              <div className="stack-list">
                <article className="list-card">
                  <div className="row spread">
                    <h4>{selectedCandidate.name}</h4>
                    {selectedCandidate.verdict ? <StatusChip value={selectedCandidate.verdict} /> : <span className="meta-pill">sin verdict</span>}
                  </div>
                  <p>{selectedCandidate.summary || selectedCandidate.hypothesis || "Sin summary ni hypothesis persistidos."}</p>
                  <KeyValueList
                    items={[
                      { label: "slug", value: selectedCandidate.slug },
                      { label: "focus", value: selectedCandidate.focus || "—" },
                      { label: "scope", value: selectedCandidate.scope || "—" },
                      { label: "maturity", value: selectedCandidate.maturity || "—" },
                      { label: "priority", value: selectedCandidate.priority ?? "—" },
                      { label: "updated_at", value: formatDateTime(selectedCandidate.updated_at) },
                    ]}
                  />
                  <div className="json-block-group">
                    <div>
                      <span className="eyebrow">scorecard</span>
                      <pre className="json-block">{prettyJson(selectedCandidate.scorecard)}</pre>
                    </div>
                    <div>
                      <span className="eyebrow">gates</span>
                      <pre className="json-block">{prettyJson(selectedCandidate.gates)}</pre>
                    </div>
                    <div>
                      <span className="eyebrow">next_research</span>
                      <pre className="json-block">{prettyJson(selectedCandidate.next_research)}</pre>
                    </div>
                    <div>
                      <span className="eyebrow">kill_criteria</span>
                      <pre className="json-block">{prettyJson(selectedCandidate.kill_criteria)}</pre>
                    </div>
                  </div>
                  <div className="stack-list compact">
                    <div>
                      <span className="eyebrow">Decision memo</span>
                      <p>{selectedCandidate.decision_memo || "—"}</p>
                    </div>
                  </div>
                </article>
              </div>

              <div className="stack-list">
                <Section title="Evidence" eyebrow="Linked rows" stagger={4} aside={<span className="meta-pill">{evidence.length}</span>}>
                  {selectedEvidenceQuery.isLoading ? (
                    <SkeletonBlock height={180} />
                  ) : evidence.length === 0 ? (
                    <StateScreen title="Sin evidence" body="Todavía no hay evidence persistida para esta candidate." />
                  ) : (
                    <div className="stack-list compact">
                      {evidence.map((item) => (
                        <article className="list-card" key={item.id}>
                          <div className="row spread">
                            <h4>{item.title || item.kind}</h4>
                            <span className="meta-pill">{item.kind}</span>
                          </div>
                          <p>{item.claim || item.notes || "Sin claim persistido."}</p>
                          <div className="meta-row">
                            <span>{item.source_name || "source n/a"}</span>
                            <span>{item.confidence !== null ? `confidence ${item.confidence}` : "sin confidence"}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </Section>

                <Section title="Apply logs" eyebrow="Candidate scoped" stagger={5} aside={<span className="meta-pill">{candidateLogs.length}</span>}>
                  {selectedLogsQuery.isLoading ? (
                    <SkeletonBlock height={180} />
                  ) : candidateLogs.length === 0 ? (
                    <StateScreen title="Sin logs de apply" body="Todavía no hay imports manuales asociados a esta candidate." />
                  ) : (
                    <div className="stack-list compact">
                      {candidateLogs.map((item) => (
                        <article className="list-card" key={item.id}>
                          <div className="row spread">
                            <h4>{item.id}</h4>
                            <StatusChip value={item.status} />
                          </div>
                          <p>{item.error_message || item.notes || item.recognized_format || "Sin detalle adicional."}</p>
                          <div className="meta-row">
                            <span>{item.source_type}</span>
                            <span>{formatDateTime(item.created_at)}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </Section>
              </div>
            </div>
          ) : (
            <StateScreen title="Candidate no encontrada" body="La candidate seleccionada ya no existe o no pudo cargarse." tone="bad" />
          )}
        </Section>
      </div>
    </RadarShell>
  );
}

function LangfuseTraceCard({
  item,
  index,
}: {
  item: LangfuseTraceItem;
  index: number;
}) {
  return (
    <article className="list-card reveal" style={{ "--stagger": index } as React.CSSProperties}>
      <div className="row spread">
        <h4>{item.project_name || item.project_id || "Sin proyecto"}</h4>
        <StatusChip value={item.langfuse_status || "unknown"} />
      </div>
      <p>{item.summary || item.prompt_ref || item.langfuse_trace_id || "Sin detalle persistido."}</p>
      <dl className="key-value-list">
        <div>
          <dt>agent</dt>
          <dd>{item.agent}{item.mode ? ` · ${item.mode}` : ""}</dd>
        </div>
        <div>
          <dt>prompt</dt>
          <dd>{item.prompt_name || item.prompt_ref || "—"}</dd>
        </div>
        <div>
          <dt>source</dt>
          <dd>{item.prompt_source || "unknown"}</dd>
        </div>
        <div>
          <dt>trace</dt>
          <dd>{item.langfuse_trace_id || "—"}</dd>
        </div>
      </dl>
      {item.langfuse_error ? <p className="form-error">{item.langfuse_error}</p> : null}
    </article>
  );
}

function LangfusePage() {
  const [filters, setFilters] = useState({
    project_id: "",
    agent: "",
    prompt_source: "",
    langfuse_status: "",
  });
  const deferredFilters = useDeferredValue(filters);
  const summaryQuery = useQuery({
    queryKey: ["dashboard-langfuse-summary"],
    queryFn: getLangfuseSummary,
  });
  const promptsQuery = useQuery({
    queryKey: ["dashboard-langfuse-prompts"],
    queryFn: getLangfusePrompts,
  });
  const tracesQuery = useQuery({
    queryKey: ["dashboard-langfuse-traces", deferredFilters],
    queryFn: () => getLangfuseTraces(deferredFilters),
  });

  const summary = summaryQuery.data as LangfuseSummaryResponse | undefined;
  const prompts = (promptsQuery.data as LangfusePromptsResponse | undefined)?.items || [];
  const tracesData = tracesQuery.data as LangfuseTracesResponse | undefined;
  const traces = tracesData?.items || [];
  const langfuseBaseUrl =
    summary?.langfuse_base_url ||
    tracesData?.langfuse_base_url ||
    (promptsQuery.data as LangfusePromptsResponse | undefined)?.langfuse_base_url ||
    null;

  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  useEffect(() => {
    if (!traces.length) {
      if (selectedTraceId !== null) {
        setSelectedTraceId(null);
      }
      return;
    }
    if (!selectedTraceId || !traces.some((item) => item.run_id === selectedTraceId)) {
      setSelectedTraceId(traces[0]?.run_id || null);
    }
  }, [traces, selectedTraceId]);

  const selectedTrace = traces.find((item) => item.run_id === selectedTraceId) || null;
  const queryError = summaryQuery.isError
    ? summaryQuery.error
    : promptsQuery.isError
      ? promptsQuery.error
      : tracesQuery.isError
        ? tracesQuery.error
        : null;

  if (summaryQuery.isLoading || promptsQuery.isLoading || tracesQuery.isLoading) {
    return (
      <AppShell title="Prompts & Traces" subtitle="Superficie read-only de Langfuse usando primero los datos persistidos en runs.">
        <SkeletonBlock height={220} />
        <SkeletonBlock height={520} />
      </AppShell>
    );
  }

  if (queryError || !summary) {
    return (
      <AppShell title="Prompts & Traces" subtitle="Superficie read-only de Langfuse usando primero los datos persistidos en runs.">
        <StateScreen
          title="No pude cargar prompts y traces"
          body={queryError ? queryError.message : "Langfuse summary missing"}
          tone="bad"
        />
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Prompts & Traces"
      subtitle="Catálogo de prompts y trazas recientes construido desde `prompt_ref`, `langfuse_trace_id` y `metadata.langfuse_*` ya persistidos en runs."
    >
      <div className="kpi-grid langfuse-kpis">
        <KpiCard label="Observed runs" value={summary.kpis.observed_runs} note="runs con señal Langfuse persistida" stagger={0} />
        <KpiCard label="Unique prompts" value={summary.kpis.unique_prompts} note="refs distintas vistas en runs" stagger={1} />
        <KpiCard label="Traced runs" value={summary.kpis.traced_runs} note="corridas con trace_id persistido" stagger={2} />
        <KpiCard label="Fallback runs" value={summary.kpis.fallback_runs} note="prompt fallback detectado en metadata" stagger={3} />
        <KpiCard label="Error runs" value={summary.kpis.error_runs} note="langfuse_error o status de error" stagger={4} />
      </div>

      <div className="dashboard-grid">
        <Section
          title="Prompt sources"
          eyebrow="Persisted metadata"
          stagger={1}
          aside={
            langfuseBaseUrl ? (
              <a className="secondary-button" href={langfuseBaseUrl} rel="noreferrer" target="_blank">
                Open Langfuse
              </a>
            ) : undefined
          }
        >
          {summary.prompt_sources.length === 0 ? (
            <StateScreen title="Sin señales de prompts" body="Todavía no hay runs con `prompt_ref` o metadata Langfuse persistida." />
          ) : (
            <div className="stack-list compact">
              {summary.prompt_sources.map((item, index) => (
                <article className="list-card reveal" key={item.source} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <h4>{item.source}</h4>
                    <span className="meta-pill">{formatNumber(item.count)} runs</span>
                  </div>
                  <p>Fuente persistida de prompt usada por el runtime.</p>
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="Langfuse statuses" eyebrow="Persisted health" stagger={2}>
          {summary.langfuse_statuses.length === 0 ? (
            <StateScreen title="Sin statuses" body="Todavía no hay metadata de Langfuse para agrupar." />
          ) : (
            <div className="stack-list compact">
              {summary.langfuse_statuses.map((item, index) => (
                <article className="list-card reveal" key={item.status} style={{ "--stagger": index } as React.CSSProperties}>
                  <div className="row spread">
                    <h4>{item.status}</h4>
                    <StatusChip value={item.status} live={item.status === "traced"} />
                  </div>
                  <p>{formatNumber(item.count)} runs con este estado persistido.</p>
                </article>
              ))}
            </div>
          )}
        </Section>
      </div>

      <Section title="Prompt catalog" eyebrow="Read-only from runs" stagger={3} aside={<span className="meta-pill">{prompts.length} prompt refs</span>}>
        {prompts.length === 0 ? (
          <StateScreen title="Sin prompt refs" body="Todavía no hay prompt refs persistidos en runs." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>prompt</th>
                  <th>runs</th>
                  <th>last used</th>
                  <th>source</th>
                  <th>status</th>
                  <th>last project</th>
                  <th>last trace</th>
                </tr>
              </thead>
              <tbody>
                {prompts.map((item) => (
                  <tr key={item.prompt_ref}>
                    <td>
                      <strong>{item.prompt_name || item.prompt_ref}</strong>
                      <div className="cell-subtitle">{item.prompt_ref}</div>
                    </td>
                    <td>{formatNumber(item.runs_count)}</td>
                    <td>{formatDateTime(item.last_used_at)}</td>
                    <td>{item.last_prompt_source || "unknown"}</td>
                    <td>
                      <StatusChip
                        value={item.last_prompt_fallback ? "fallback" : item.last_langfuse_status || "unknown"}
                        live={item.last_langfuse_status === "traced"}
                      />
                    </td>
                    <td>{item.last_project_name || item.last_project_id || "—"}</td>
                    <td>{item.last_trace_id || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Recent traces" eyebrow="Runs-derived table" stagger={4} aside={<span className="meta-pill">{traces.length} rows</span>}>
        <div className="filters">
          <input
            value={filters.project_id}
            onChange={(event) => setFilters((current) => ({ ...current, project_id: event.target.value }))}
            placeholder="project_id"
          />
          <input
            value={filters.agent}
            onChange={(event) => setFilters((current) => ({ ...current, agent: event.target.value }))}
            placeholder="agent"
          />
          <select
            value={filters.prompt_source}
            onChange={(event) => setFilters((current) => ({ ...current, prompt_source: event.target.value }))}
          >
            <option value="">Todos los prompt_source</option>
            <option value="langfuse">langfuse</option>
            <option value="langfuse-fallback">langfuse-fallback</option>
            <option value="repo-local">repo-local</option>
          </select>
          <select
            value={filters.langfuse_status}
            onChange={(event) => setFilters((current) => ({ ...current, langfuse_status: event.target.value }))}
          >
            <option value="">Todos los langfuse_status</option>
            <option value="traced">traced</option>
            <option value="disabled">disabled</option>
            <option value="trace-error">trace-error</option>
          </select>
        </div>

        {traces.length === 0 ? (
          <StateScreen title="Sin traces para los filtros" body="No hay runs Langfuse-relevant para los filtros actuales." />
        ) : (
          <div className="detail-layout">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>project</th>
                    <th>agent</th>
                    <th>prompt</th>
                    <th>source</th>
                    <th>status</th>
                    <th>trace</th>
                    <th>started</th>
                  </tr>
                </thead>
                <tbody>
                  {traces.map((item) => (
                    <tr
                      key={item.run_id}
                      className={item.run_id === selectedTrace?.run_id ? "selected-row" : ""}
                      onClick={() => setSelectedTraceId(item.run_id)}
                    >
                      <td>{item.project_name || item.project_id || "—"}</td>
                      <td>{item.agent}{item.mode ? ` · ${item.mode}` : ""}</td>
                      <td>{item.prompt_name || item.prompt_ref || "—"}</td>
                      <td>{item.prompt_source || "unknown"}</td>
                      <td>
                        <StatusChip
                          value={item.prompt_fallback ? "fallback" : item.langfuse_status || "unknown"}
                          live={item.langfuse_status === "traced"}
                        />
                      </td>
                      <td>{item.langfuse_trace_id || "—"}</td>
                      <td>{formatDateTime(item.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="detail-panel">
              {selectedTrace ? (
                <Section title="Trace detail" eyebrow="Selected run" stagger={5}>
                  <div className="stack-list compact">
                    <article className="list-card">
                      <div className="row spread">
                        <h4>{selectedTrace.project_name || selectedTrace.project_id || "Sin proyecto"}</h4>
                        <StatusChip
                          value={selectedTrace.prompt_fallback ? "fallback" : selectedTrace.langfuse_status || "unknown"}
                          live={selectedTrace.langfuse_status === "traced"}
                        />
                      </div>
                      <p>{selectedTrace.summary || "No hay summary persistido para este run."}</p>
                      <dl className="key-value-list">
                        <div>
                          <dt>run_id</dt>
                          <dd>{selectedTrace.run_id}</dd>
                        </div>
                        <div>
                          <dt>agent</dt>
                          <dd>{selectedTrace.agent}{selectedTrace.mode ? ` · ${selectedTrace.mode}` : ""}</dd>
                        </div>
                        <div>
                          <dt>prompt_ref</dt>
                          <dd>{selectedTrace.prompt_ref || "—"}</dd>
                        </div>
                        <div>
                          <dt>prompt_source</dt>
                          <dd>{selectedTrace.prompt_source || "unknown"}</dd>
                        </div>
                        <div>
                          <dt>prompt_fallback</dt>
                          <dd>{selectedTrace.prompt_fallback ? "true" : "false"}</dd>
                        </div>
                        <div>
                          <dt>trace_id</dt>
                          <dd>{selectedTrace.langfuse_trace_id || "—"}</dd>
                        </div>
                        <div>
                          <dt>started</dt>
                          <dd>{formatDateTime(selectedTrace.started_at)}</dd>
                        </div>
                        <div>
                          <dt>ended</dt>
                          <dd>{formatDateTime(selectedTrace.ended_at)}</dd>
                        </div>
                      </dl>
                      {selectedTrace.langfuse_error ? <p className="form-error">{selectedTrace.langfuse_error}</p> : null}
                      {langfuseBaseUrl ? (
                        <div className="hero-actions">
                          <a className="secondary-button" href={langfuseBaseUrl} rel="noreferrer" target="_blank">
                            Open Langfuse root
                          </a>
                        </div>
                      ) : null}
                    </article>
                  </div>
                </Section>
              ) : (
                <StateScreen title="Sin trace seleccionado" body="Elegí una fila para ver el detalle persistido del run." />
              )}
            </div>
          </div>
        )}
      </Section>

      <div className="dashboard-grid">
        <Section title="Recent fallbacks" eyebrow="Prompt fallback" stagger={6}>
          {summary.recent_fallbacks.length === 0 ? (
            <StateScreen title="Sin fallbacks recientes" body="No hay prompt fallbacks persistidos en los runs observados." />
          ) : (
            <div className="stack-list compact">
              {summary.recent_fallbacks.map((item, index) => (
                <LangfuseTraceCard item={item} index={index} key={`fallback-${item.run_id}`} />
              ))}
            </div>
          )}
        </Section>

        <Section title="Recent errors" eyebrow="Langfuse issues" stagger={7}>
          {summary.recent_errors.length === 0 ? (
            <StateScreen title="Sin errores recientes" body="No hay `langfuse_error` persistidos ni status de error en los runs observados." />
          ) : (
            <div className="stack-list compact">
              {summary.recent_errors.map((item, index) => (
                <LangfuseTraceCard item={item} index={index} key={`error-${item.run_id}`} />
              ))}
            </div>
          )}
        </Section>
      </div>
    </AppShell>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<OverviewPage />} />
      <Route path="/dashboard/activity" element={<ActivityFeedPage />} />
      <Route path="/radar" element={<RadarOverviewPage />} />
      <Route path="/radar/candidates" element={<RadarCandidatesPage />} />
      <Route path="/radar/candidates/:candidateId" element={<RadarCandidateDetailPage />} />
      <Route path="/radar/portfolio" element={<RadarPortfolioPage />} />
      <Route path="/radar/prompts" element={<RadarPromptsPage />} />
      <Route path="/radar/prompts/:promptId" element={<RadarPromptDetailPage />} />
      <Route path="/radar/prompt-runs" element={<RadarPromptRunsPage />} />
      <Route path="/radar/import" element={<RadarImportPage />} />
      <Route path="/radar/apply-logs" element={<RadarApplyLogsPage />} />
      <Route path="/radar/settings" element={<RadarSettingsPage />} />
      <Route path="/dashboard/projects" element={<ProjectsPage />} />
      <Route path="/dashboard/projects/:projectId" element={<ProjectDetailPage />} />
      <Route path="/dashboard/runs" element={<RunsPage />} />
      <Route path="/dashboard/handoffs" element={<HandoffsPage />} />
      <Route path="/dashboard/ideas" element={<IdeasPage />} />
      <Route path="/dashboard/research" element={<ResearchPageF4B />} />
      <Route path="/dashboard/langfuse" element={<LangfusePage />} />
      <Route path="/dashboard/notifications" element={<NotificationsPage />} />
      <Route path="/dashboard/system" element={<SystemPage />} />
      <Route
        path="*"
        element={
          <AppShell title="Not found" subtitle="La ruta no existe dentro del dashboard F7B.">
            <StateScreen title="Ruta no encontrada" body="Volvé a Overview, Activity, Projects, Runs, Handoffs, Ideas, Research, Prompts & Traces, Notifications o System." tone="bad" />
          </AppShell>
        }
      />
    </Routes>
  );
}
